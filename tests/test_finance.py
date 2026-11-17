import copy
import unittest

from cash_planner.finance import annual_metrics, choose_fact


def fixture():
    facts = {}
    for tag, value in [("Revenues", 730), ("CostOfRevenue", 365),
                       ("InventoryNet", 100), ("AccountsReceivableNetCurrent", 80),
                       ("AccountsPayableCurrent", 60)]:
        row = dict(end="2023-12-31", val=value, form="10-K", filed="2024-02-01",
                   accn="0000000001-24-000001", fy=2023, fp="FY")
        if tag in ("Revenues", "CostOfRevenue"):
            row["start"] = "2023-01-01"
            rows = [row]
        else:
            rows = [dict(row, end="2022-12-31", val=value / 2), row]
        facts[tag] = {"units": {"USD": rows}}
    return {"cik": 1, "entityName": "Example", "facts": {"us-gaap": facts}}


class FinanceTests(unittest.TestCase):
    def test_average_balances_and_inclusive_year(self):
        row = annual_metrics(fixture(), years=1)[0]
        self.assertEqual(row["days"], 365)
        self.assertEqual(row["dio"], 75)
        self.assertEqual(row["dso"], 30)
        self.assertEqual(row["dpo"], 45)
        self.assertEqual(row["ccc"], 60)
        self.assertEqual(row["release_5_days"], 5)

    def test_latest_amendment_wins_and_duplicate_is_harmless(self):
        data = fixture()
        rows = data["facts"]["us-gaap"]["InventoryNet"]["units"]["USD"]
        rows.extend([dict(rows[-1], val=120, filed="2024-03-01", form="10-K/A"), rows[-1]])
        self.assertEqual(annual_metrics(data, years=1)[0]["dio"], 85)

    def test_missing_opening_is_flagged_not_zero_filled(self):
        data = fixture()
        data["facts"]["us-gaap"]["InventoryNet"]["units"]["USD"].pop(0)
        row = annual_metrics(data, years=1)[0]
        self.assertIsNone(row["dio"])
        self.assertIsNone(row["ccc"])
        self.assertTrue(any("opening inventory" in flag for flag in row["flags"]))

    def test_zero_denominator(self):
        data = fixture()
        data["facts"]["us-gaap"]["CostOfRevenue"]["units"]["USD"][0]["val"] = 0
        row = annual_metrics(data, years=1)[0]
        self.assertIsNone(row["dpo"])
        self.assertIsNone(row["release_5_days"])

    def test_missing_revenue_keeps_cost_period_and_flags_ratios(self):
        data = fixture()
        del data["facts"]["us-gaap"]["Revenues"]
        row = annual_metrics(data, years=1)[0]
        self.assertIsNone(row["dso"])
        self.assertEqual(row["dio"], 75)
        self.assertIn("Missing revenue USD fact", row["flags"])

    def test_leap_and_53_week_year_lengths(self):
        from cash_planner.finance import period_days
        self.assertEqual(period_days("2024-01-01", "2024-12-31"), 366)
        self.assertEqual(period_days("2020-06-28", "2021-07-03"), 371)

    def test_conflicting_identical_provenance_raises(self):
        data = fixture()
        rows = data["facts"]["us-gaap"]["InventoryNet"]["units"]["USD"]
        rows.append(dict(rows[-1], val=999))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            choose_fact(data, ["InventoryNet"], "2023-12-31")

    def test_quarterly_comparative_and_other_units_ignored(self):
        data = fixture()
        source = data["facts"]["us-gaap"]["Revenues"]["units"]
        source["EUR"] = copy.deepcopy(source["USD"])
        source["USD"].append(dict(source["USD"][0], start="2023-10-01", val=900,
                                  filed="2025-01-01"))
        self.assertEqual(annual_metrics(data, years=1)[0]["revenue"], 730)


if __name__ == "__main__":
    unittest.main()
