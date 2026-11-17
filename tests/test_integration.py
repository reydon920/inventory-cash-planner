import csv
from datetime import date, timedelta
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from tests import temporary_directory

from PIL import Image

from cash_planner.charts import showcase
from cash_planner.data import SAMPLE, load_analysis
from cash_planner.finance import annual_metrics
from cash_planner.report import write_report


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []

    def handle_starttag(self, tag, attributes):
        for name, value in attributes:
            if name == "src" or (tag == "link" and name == "href"):
                self.resources.append(value)


class IntegrationTests(unittest.TestCase):
    def test_arrow_2024_matches_independent_filing_transcription(self):
        expected = json.loads((SAMPLE / "arrow-2024-reconciliation.json").read_text())
        rows = annual_metrics(json.loads((SAMPLE / "arrow.json").read_text()))
        actual = next(row for row in rows if row["end"] == expected["end"])
        self.assertEqual(actual["days"], expected["days"])
        for label, fact in actual["sources"].items():
            self.assertEqual(fact["val"], expected[label], label)
        # A separate calculation using the original filing's displayed units.
        dio = (5187225 + 4709706) / 2 / 24630916 * 366
        dso = (12238073 + 13030991) / 2 / 27923324 * 366
        dpo = (10070015 + 11047470) / 2 / 24630916 * 366
        self.assertAlmostEqual(actual["ccc"], dio + dso - dpo)
        self.assertAlmostEqual(actual["release_5_days"], 24630916 * 1000 / 366 * 5)

    def test_sample_has_five_years_per_company_and_daily_calendar(self):
        result = load_analysis()
        for rows in result["companies"].values():
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["ccc"] is not None for row in rows))
        with (SAMPLE / "demand.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        start = date.fromisoformat(rows[0]["date"])
        self.assertEqual([row["date"] for row in rows], [(start + timedelta(days=i)).isoformat() for i in range(len(rows))])
        self.assertTrue(any(int(row["units"]) == 0 for row in rows))
        self.assertEqual(result["assumptions"]["training_days"], 90)
        self.assertEqual(result["assumptions"]["testing_days"], 284)

    def test_future_sales_do_not_change_forecast_or_first_order(self):
        baseline = load_analysis()
        with temporary_directory() as folder:
            sample = Path(folder) / "sample"
            shutil.copytree(SAMPLE, sample)
            content = (sample / "demand.csv").read_text().splitlines()
            content[-1] = "2011-12-09,999999"
            (sample / "demand.csv").write_text("\n".join(content) + "\n")
            changed = load_analysis(sample)
        self.assertEqual(baseline["assumptions"], changed["assumptions"])
        for original, later in zip(baseline["policies"], changed["policies"]):
            self.assertEqual(original["daily"][0], later["daily"][0])

    def test_cost_only_scales_cash_not_service(self):
        baseline, double_cost = load_analysis(unit_cost=1), load_analysis(unit_cost=2)
        for first, second in zip(baseline["policies"], double_cost["policies"]):
            self.assertEqual(first["fill_rate"], second["fill_rate"])
            self.assertEqual(first["cash_gbp"] * 2, second["cash_gbp"])

    def test_corrupt_daily_sample_is_rejected(self):
        for change in ("missing", "duplicate", "negative_training"):
            with self.subTest(change=change), temporary_directory() as folder:
                sample = folder / "sample"
                shutil.copytree(SAMPLE, sample)
                rows = (sample / "demand.csv").read_text().splitlines()
                if change == "missing":
                    del rows[10]
                elif change == "duplicate":
                    rows[10] = rows[9]
                else:
                    rows[1] = "2010-12-01,-1"
                (sample / "demand.csv").write_text("\n".join(rows) + "\n")
                with self.assertRaises(ValueError):
                    load_analysis(sample)

    def test_report_and_three_large_images_work_without_network(self):
        with temporary_directory() as folder, patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            result = load_analysis()
            output = write_report(result, Path(folder) / "report.html")
            html = output.read_text(encoding="utf-8")
            parser = Resources()
            parser.feed(html)
            self.assertEqual(len(parser.resources), 3)
            self.assertTrue(all(value.startswith("data:image/png;base64,") for value in parser.resources))
            self.assertNotIn("<script src=", html)
            self.assertIn("0001558370-25-000781", html)
            for path in showcase(result, Path(folder) / "showcase"):
                with Image.open(path) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertGreaterEqual(image.width, 1000)
                    self.assertGreaterEqual(image.height, 700)
                    image.verify()
            exported = json.loads((Path(folder) / "results.json").read_text())
            self.assertEqual(exported["policies"][0]["served"], result["policies"][0]["served"])
            with (Path(folder) / "financials.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 10)


if __name__ == "__main__":
    unittest.main()
