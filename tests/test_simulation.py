import unittest

from cash_planner.simulation import simulate


class SimulationTests(unittest.TestCase):
    def test_lost_sales_and_later_arrival(self):
        result = simulate([10, 10, 10], forecast=10, lead_days=2, safety_days=0,
                          unit_cost=2, policy="weekly", initial_stock=0)
        self.assertEqual(result["served"], 10)
        self.assertEqual(result["lost"], 20)
        self.assertEqual([x["received"] for x in result["daily"]], [0, 0, 90])
        self.assertAlmostEqual(result["fill_rate"], 1 / 3)

    def test_inventory_position_prevents_repeated_orders(self):
        result = simulate([0] * 5, forecast=10, lead_days=3, safety_days=1,
                          unit_cost=1, policy="reorder", initial_stock=0)
        self.assertEqual(result["orders"], 1)

    def test_daily_conservation(self):
        for policy in ("weekly", "reorder"):
            result = simulate([2, 9, 0, 8, 30, 1] * 5, forecast=5, lead_days=2,
                              safety_days=2, unit_cost=3, policy=policy)
            previous = result["initial_stock"]
            for row in result["daily"]:
                self.assertEqual(previous + row["received"] - row["served"], row["stock"])
                self.assertEqual(row["served"] + row["lost"], row["demand"])
                previous = row["stock"]

    def test_invalid_inputs(self):
        for kwargs in ({"lead_days": 0}, {"safety_days": -1}, {"unit_cost": float("nan")},
                       {"policy": "magic"}, {"lead_days": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulate([1], forecast=1, **kwargs)
        for demand in ([], [-1], [float("inf")]):
            with self.assertRaises(ValueError):
                simulate(demand, forecast=1)

    def test_zero_demand_has_no_fill_rate_or_inventory_days(self):
        row = simulate([0, 0], forecast=0)
        self.assertIsNone(row["fill_rate"])
        self.assertIsNone(row["inventory_days"])


if __name__ == "__main__":
    unittest.main()
