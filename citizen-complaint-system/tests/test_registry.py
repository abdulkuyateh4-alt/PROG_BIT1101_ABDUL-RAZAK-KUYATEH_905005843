"""Unit tests for the ComplaintRegistry, the add/display functions and the CLI."""

import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

import main
from ccs import (
    Citizen,
    Complaint,
    ComplaintRegistry,
    GovernmentOfficer,
    add_record,
    display_records,
)

TEXT = "Street lights on our road have not worked for a month."


def reset_ids() -> None:
    for cls in (Citizen, Complaint, GovernmentOfficer):
        cls.reset_counter()


class TestAddAndLookUp(unittest.TestCase):
    def setUp(self) -> None:
        reset_ids()
        self.registry = ComplaintRegistry()
        self.citizen = Citizen("Bo")
        self.officer = GovernmentOfficer("Electricity Distribution and Supply Authority", "Bo")
        self.complaint = self.citizen.submit_complaint("Electricity", TEXT)

    def test_add_record_stores_objects_by_code(self) -> None:
        self.assertEqual(add_record(self.registry, self.citizen), "CIT-0001")
        self.assertEqual(add_record(self.registry, self.officer), "OFF-0001")
        self.assertEqual(add_record(self.registry, self.complaint), "CMP-0001")
        self.assertIs(self.registry.get_complaint(" cmp-0001 "), self.complaint)
        self.assertIs(self.registry.get_citizen("cit-0001"), self.citizen)
        self.assertIs(self.registry.get_officer("OFF-0001"), self.officer)
        self.assertIsNone(self.registry.get_complaint("CMP-9999"))
        self.assertEqual(len(self.registry), 1)
        for code in ("CMP-0001", "cit-0001", "OFF-0001"):
            self.assertIn(code, self.registry)
        self.assertEqual(tuple(self.registry), (self.complaint,))

    def test_rejects_duplicates_orphans_and_wrong_types(self) -> None:
        with self.assertRaises(ValueError):
            add_record(self.registry, self.complaint)      # citizen not registered yet
        add_record(self.registry, self.citizen)
        with self.assertRaises(ValueError):
            add_record(self.registry, self.citizen)        # duplicate
        with self.assertRaises(TypeError):
            add_record(self.registry, "CIT-0001")  # type: ignore[arg-type]

    def test_display_functions(self) -> None:
        self.assertEqual(self.registry.display_complaints(), "No complaints submitted yet.")
        self.assertEqual(self.registry.display_citizens(), "No citizens registered yet.")
        self.assertEqual(self.registry.display_officers(), "No officers registered yet.")
        for record in (self.citizen, self.officer, self.complaint):
            add_record(self.registry, record)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            display_records(self.registry)
        output = buffer.getvalue()
        for code in ("CIT-0001", "OFF-0001", "CMP-0001"):
            self.assertIn(code, output)


class TestReports(unittest.TestCase):
    def setUp(self) -> None:
        reset_ids()
        self.registry = ComplaintRegistry.with_sample_data()

    def test_sample_data_loaded(self) -> None:
        counts = (len(self.registry.citizens()), len(self.registry.officers()), len(self.registry))
        self.assertEqual(counts, (6, 4, 10))

    def test_counts_and_rates(self) -> None:
        statuses = dict(self.registry.count_by("status"))
        self.assertEqual(statuses, {"Resolved": 3, "Submitted": 3, "Under review": 2,
                                    "In progress": 1, "Rejected": 1})
        self.assertEqual(self.registry.resolution_rate(), 30.0)
        self.assertEqual(self.registry.average_days_to_resolve(), 7.0)
        self.assertEqual(len(self.registry.open_complaints()), 6)
        with self.assertRaises(ValueError):
            self.registry.count_by("description")
        table = ComplaintRegistry.format_counts(self.registry.count_by("category"), "Category")
        self.assertIn("Total", table)
        self.assertEqual(ComplaintRegistry().resolution_rate(), 0.0)
        self.assertIsNone(ComplaintRegistry().average_days_to_resolve())

    def test_overdue_and_department_lists(self) -> None:
        overdue = self.registry.overdue_complaints(date(2026, 10, 19))
        self.assertEqual(tuple(c.complaint_id for c in overdue),
                         ("CMP-0003", "CMP-0004", "CMP-0005", "CMP-0006", "CMP-0008"))
        roads = self.registry.complaints_for_department("Sierra Leone Roads Authority")
        self.assertEqual(len(roads), 2)

    def test_staff_view_protects_confidential_reports(self) -> None:
        self.assertNotIn("CMP-0006", self.registry.display_citizens())
        self.assertIn("(confidential)", self.registry.display_complaints())

    def test_public_export_contains_only_totals(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "public.csv"
            rows = self.registry.export_public_statistics(path)
            content = path.read_text(encoding="utf-8")
            with path.open(encoding="utf-8", newline="") as handle:
                table = tuple(tuple(r) for r in csv.reader(handle))
        self.assertEqual(rows, 7)
        self.assertEqual(table[0], ComplaintRegistry.EXPORT_COLUMNS)
        self.assertIn(("Western Area Urban", "Roads", "2", "0", "1", "1"), table)
        for private in ("CIT-", "OFF-", "CMP-", "pothole", "2026"):
            self.assertNotIn(private, content)


class TestCommandLine(unittest.TestCase):
    """Drive the interactive program with scripted keyboard input."""

    def run_cli(self, *answers: str) -> str:
        reset_ids()
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=answers), redirect_stdout(buffer):
            self.assertEqual(main.run(), 0)
        return buffer.getvalue()

    def test_full_workflow(self) -> None:
        output = self.run_cli(
            "1", "16", "2",                          # citizen, Western Area Urban, Krio
            "2", "CIT-0001", "1", "", "3", "Large potholes near the market.",
            "4", "Sierra Leone Roads Authority", "Western Area Urban",
            "5", "OFF-0001", "CMP-0001", "1", "Inspection booked.",
            "3", "cmp-0001",
            "0",
        )
        self.assertIn("citizen code CIT-0001", output)
        self.assertIn("complaint CMP-0001 submitted", output)
        self.assertIn("sent to: Sierra Leone Roads Authority", output)
        self.assertIn("Target response time for High priority: 7 days", output)
        self.assertIn("staff code OFF-0001", output)
        self.assertIn("CMP-0001 is now 'Under review'", output)
        self.assertIn("Inspection booked.", output)
        self.assertIn("Goodbye", output)

    def test_privacy_and_wrong_department_are_explained(self) -> None:
        output = self.run_cli(
            "1", "Bo", "",
            "2", "CIT-0001", "Water supply", "", "", "Call 076123456 now", "Pump broken for days.",
            "4", "Sierra Leone Police", "Bo",
            "5", "OFF-0001", "CMP-0001", "x", "y",
            "0",
        )
        self.assertIn("For privacy, the description must not contain phone numbers", output)
        self.assertIn("complaint CMP-0001 submitted", output)
        self.assertIn("This complaint belongs to Ministry of Water Resources", output)
        self.assertIn("Too many invalid attempts", output)

    def test_closing_requires_a_note(self) -> None:
        output = self.run_cli(
            "1", "Bo", "", "2", "CIT-0001", "Other", "", "Low", "General service complaint.",
            "4", "Office of the Ombudsman", "Bo",
            "5", "OFF-0001", "CMP-0001", "Rejected", "", "Not a public service issue.",
            "0",
        )
        self.assertIn("A note explaining the outcome is required", output)
        self.assertIn("CMP-0001 is now 'Rejected'", output)

    def test_invalid_menu_and_missing_records(self) -> None:
        output = self.run_cli("x", "2", "5", "3", "CMP-0404", "0")
        self.assertIn("please type a number from 0 to 10", output)
        self.assertIn("Please register as a citizen first", output)
        self.assertIn("This needs at least one officer", output)
        self.assertIn("No complaint with that code", output)

    def test_end_of_input_exits_cleanly(self) -> None:
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=EOFError), redirect_stdout(buffer):
            self.assertEqual(main.run(), 0)
        self.assertIn("Goodbye", buffer.getvalue())

    def test_sample_data_reports_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.object(
            main, "EXPORT_FILE", str(Path(folder) / "stats.csv")
        ):
            output = self.run_cli("10", "6", "7", "8", "9", "0")
        self.assertIn("Loaded 6 citizens, 4 officers and 10 complaints", output)
        self.assertIn("OVERDUE", output)
        self.assertIn("Resolution rate: 30.0%", output)
        self.assertIn("7 row(s) written", output)


if __name__ == "__main__":
    unittest.main()
