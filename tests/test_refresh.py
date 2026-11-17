from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile
from datetime import datetime
from tests import temporary_directory

from openpyxl import Workbook

from scripts.refresh_data import download, retail_extract


class RefreshTests(unittest.TestCase):
    def test_retry_transient_error_and_identify_requests(self):
        response = BytesIO(b'{"public":"data"}')
        error = HTTPError("https://example.org", 503, "busy", {"Retry-After": "0"}, None)
        with temporary_directory() as folder, patch("scripts.refresh_data.time.sleep"), patch(
            "scripts.refresh_data.urlopen", side_effect=[error, response]
        ) as request:
            data = download("https://example.org", Path(folder) / "facts.json", "Research contact https://example.org")
            self.assertEqual(data, b'{"public":"data"}')
            self.assertEqual(request.call_count, 2)
            self.assertIn("Research", request.call_args.args[0].get_header("User-agent"))

    def test_forbidden_does_not_retry_or_replace_data(self):
        with temporary_directory() as folder, patch("scripts.refresh_data.time.sleep"), patch(
            "scripts.refresh_data.urlopen", side_effect=HTTPError("url", 403, "denied", {}, None)
        ) as request:
            path = Path(folder) / "cached.json"
            path.write_bytes(b"keep")
            with self.assertRaisesRegex(RuntimeError, "403"):
                download("https://example.org", path, "Research contact https://example.org")
            self.assertEqual(request.call_count, 1)
            self.assertEqual(path.read_bytes(), b"keep")

    def test_uci_filter_aggregate_and_zero_fill(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["InvoiceNo", "StockCode", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID"])
        for invoice, sku, qty, price in [("1", "85123A", 10, 2), ("2", "85123A", 5, 2),
                                         ("C3", "85123A", 7, 2), ("4", "85123A", -2, 2),
                                         ("5", "85123A", 50, 0), ("6", "OTHER", 100, 2)]:
            sheet.append([invoice, sku, qty, datetime(2010, 12, 1), price, "omitted-fixture-id"])
        stream = BytesIO()
        workbook.save(stream)
        with temporary_directory() as folder:
            path = Path(folder) / "test.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Online Retail.xlsx", stream.getvalue())
            rows, count = retail_extract(path)
        self.assertEqual(count, 2)
        self.assertEqual(rows[0], {"date": "2010-12-01", "units": 15})
        self.assertEqual(rows[1]["units"], 0)
        self.assertEqual(len(rows), 374)
        self.assertNotIn("omitted-fixture-id", str(rows))


if __name__ == "__main__":
    unittest.main()
