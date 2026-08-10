import tempfile
import unittest
from pathlib import Path

from bay300_print_agent.render import render_html, write_html,write_pdf


DOCUMENT = {
    "schemaVersion": "bay300.bill-print.v1", "documentVersion": 2,
    "billNumber": "2026-000001", "store": {"name": "Lovell"},
    "customer": {"name": "Test Customer"}, "serviceTotal": "150.00",
    "serviceItems": [{"description": "Massage <script>", "employeeName": "Tom", "amount": "150.00"}],
    "tipItems": [], "tipRecipients": [{"employeeName": "Tom"}],
}


class RenderTests(unittest.TestCase):
    def test_html_is_printable_and_escaped(self):
        html = render_html(DOCUMENT, 3)
        self.assertIn("Copy 3", html)
        self.assertIn("$150.00", html)
        self.assertIn("Massage &lt;script&gt;", html)
        self.assertNotIn("Massage <script>", html)

    def test_write_creates_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_html(DOCUMENT, 1, Path(directory) / "nested" / "bill.html")
            self.assertTrue(path.exists())

    def test_pdf_is_generated_for_reliable_cups_printing(self):
        with tempfile.TemporaryDirectory() as directory:
            path=write_pdf(DOCUMENT,2,Path(directory)/"bill.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
