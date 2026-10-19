"""Unit tests for Citizen, Complaint, GovernmentOfficer and StatusUpdate.

Run all tests with:  python -m unittest discover -v
"""

import unittest
from datetime import date, timedelta

from ccs.models import (
    Citizen,
    Complaint,
    GovernmentOfficer,
    StatusUpdate,
    contains_personal_identifier,
    parse_date,
)

TEXT = "Large potholes on the main road near the market."


def reset_ids() -> None:
    for cls in (Citizen, Complaint, GovernmentOfficer):
        cls.reset_counter()


class TestHelpers(unittest.TestCase):
    def test_personal_identifier_detection(self) -> None:
        samples = (
            "076 123 456", "+232-76-123456", "call 076.123.456", "me@mail.com", "ID 12345678",
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertTrue(contains_personal_identifier(text))
        for text in ("Road 300 metres long", "Broken since 2026", "Lights off 3 weeks"):
            with self.subTest(text=text):
                self.assertFalse(contains_personal_identifier(text))

    def test_parse_date(self) -> None:
        self.assertEqual(parse_date("2026-03-15"), date(2026, 3, 15))
        self.assertEqual(parse_date(None), date.today())
        self.assertEqual(parse_date(""), date.today())
        tomorrow = date.today() + timedelta(days=1)
        for bad in ("15/03/2026", "1999-12-31", tomorrow):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_date(bad)


class TestCitizen(unittest.TestCase):
    def setUp(self) -> None:
        reset_ids()

    def test_creates_citizen(self) -> None:
        citizen = Citizen(" western area urban ", "KRIO")
        self.assertEqual(citizen.citizen_id, "CIT-0001")
        self.assertEqual((citizen.district, citizen.language), ("Western Area Urban", "Krio"))
        self.assertEqual(Citizen("Bo").language, "English")

    def test_rejects_bad_values_without_using_an_id(self) -> None:
        with self.assertRaises(ValueError):
            Citizen("Lagos")
        with self.assertRaises(ValueError):
            Citizen("Bo", "French")
        self.assertEqual(Citizen("Bo").citizen_id, "CIT-0001")

    def test_from_tuple_class_method(self) -> None:
        citizen = Citizen.from_tuple(("Bo", "Mende"))
        self.assertIsInstance(citizen, Citizen)
        self.assertEqual(citizen.language, "Mende")

    def test_submit_complaint_links_objects(self) -> None:
        citizen = Citizen("Bo")
        complaint = citizen.submit_complaint("roads", TEXT, "high", submitted_on="2026-06-02")
        self.assertIsInstance(complaint, Complaint)
        self.assertIs(complaint.citizen, citizen)
        self.assertEqual(citizen.complaint_ids, ("CMP-0001",))
        self.assertEqual(complaint.district, "Bo")
        other = citizen.submit_complaint("Roads", TEXT, district="Kenema")
        self.assertEqual(other.district, "Kenema")

    def test_update_record_is_all_or_nothing(self) -> None:
        citizen = Citizen("Bo", "Mende")
        with self.assertRaises(ValueError):
            citizen.update_record(district="Kenema", language="Spanish")
        self.assertEqual((citizen.district, citizen.language), ("Bo", "Mende"))
        citizen.update_record(district="kenema", language="english")
        self.assertEqual((citizen.district, citizen.language), ("Kenema", "English"))

    def test_display_info_hides_codes_for_staff(self) -> None:
        citizen = Citizen("Bo")
        citizen.submit_complaint("Corruption", TEXT)
        self.assertIn("CMP-0001", citizen.display_info())
        self.assertNotIn("CMP-0001", citizen.display_info(show_codes=False))


class TestComplaint(unittest.TestCase):
    def setUp(self) -> None:
        reset_ids()
        self.citizen = Citizen("Western Area Urban")
        self.complaint = self.citizen.submit_complaint(
            "Roads", TEXT, "High", submitted_on="2026-06-02"
        )
        self.officer = GovernmentOfficer("Sierra Leone Roads Authority", "Western Area Urban")

    def test_new_complaint_state(self) -> None:
        c = self.complaint
        self.assertEqual((c.complaint_id, c.status, c.priority), ("CMP-0001", "Submitted", "High"))
        self.assertEqual(c.department, "Sierra Leone Roads Authority")
        self.assertTrue(c.is_open())
        self.assertEqual(len(c.history), 1)
        self.assertIsInstance(c.history[0], StatusUpdate)

    def test_rejects_invalid_complaints(self) -> None:
        bad = (
            ("Flights", TEXT, "High"),
            ("Roads", TEXT, "Critical"),
            ("Roads", "Too short", "Low"),
            ("Roads", "x" * 301, "Low"),
            ("Roads", "Please call 076123456 now", "Low"),
        )
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.citizen.submit_complaint(*args)
        with self.assertRaises(TypeError):
            Complaint("CIT-0001", "Roads", TEXT)  # type: ignore[arg-type]
        self.assertEqual(self.citizen.complaint_ids, ("CMP-0001",))

    def test_full_workflow_and_days(self) -> None:
        self.officer.handle(self.complaint, "Under review", "", "2026-06-04")
        self.officer.handle(self.complaint, "In progress", "Crew assigned.", "2026-06-10")
        self.officer.handle(self.complaint, "Resolved", "Road repaired.", "2026-06-15")
        self.assertEqual(tuple(u.status for u in self.complaint.history),
                         ("Submitted", "Under review", "In progress", "Resolved"))
        self.assertFalse(self.complaint.is_open())
        self.assertEqual(self.complaint.days_open(), 13)
        self.assertFalse(self.complaint.is_overdue())
        self.assertEqual(self.officer.updates_made, 3)

    def test_workflow_rules(self) -> None:
        with self.assertRaises(ValueError):
            self.complaint.update_status("Resolved", "OFF-0001", "Done.")      # skips review
        with self.assertRaises(ValueError):
            self.complaint.update_status("Rejected", "OFF-0001", "")           # note required
        with self.assertRaises(ValueError):
            self.complaint.update_status("Closed", "OFF-0001", "Done.")        # unknown status
        with self.assertRaises(ValueError):
            # dated before the previous update
            self.complaint.update_status("Under review", "OFF-0001", "", "2026-06-01")
        self.complaint.update_status("Rejected", "OFF-0001", "Duplicate report.", "2026-06-03")
        with self.assertRaises(ValueError):
            self.complaint.update_status("Under review", "OFF-0001", "", "2026-06-04")  # closed
        self.assertEqual(len(self.complaint.history), 2)

    def test_history_is_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            self.complaint.history[0].status = "Resolved"  # type: ignore[misc]

    def test_overdue_uses_priority_targets(self) -> None:
        self.assertFalse(self.complaint.is_overdue(date(2026, 6, 9)))   # day 7, High = 7 days
        self.assertTrue(self.complaint.is_overdue(date(2026, 6, 10)))   # day 8
        self.assertEqual(self.complaint.days_open(date(2026, 6, 10)), 8)

    def test_confidential_reports(self) -> None:
        report = self.citizen.submit_complaint("Corruption", TEXT)
        self.assertTrue(report.is_confidential)
        self.assertEqual(report.submitted_by(), "(confidential)")
        self.assertNotIn(self.citizen.citizen_id, report.display_info())
        self.assertEqual(report.history[0].updated_by, "Citizen")
        self.assertEqual(self.complaint.submitted_by(), self.citizen.citizen_id)

    def test_static_and_class_methods(self) -> None:
        self.assertEqual(Complaint.department_for("security"), "Sierra Leone Police")
        with self.assertRaises(ValueError):
            Complaint.department_for("Flights")
        self.assertIn("Corruption", Complaint.categories())
        tidy = Complaint.validate_text("  many   spaces here ", "Note", 5, 50)
        self.assertEqual(tidy, "many spaces here")


class TestGovernmentOfficer(unittest.TestCase):
    def setUp(self) -> None:
        reset_ids()
        self.citizen = Citizen("Bo")
        self.water = self.citizen.submit_complaint("Water supply", TEXT, submitted_on="2026-08-03")

    def test_creates_officer(self) -> None:
        officer = GovernmentOfficer("sierra leone police", "bo")
        self.assertEqual(officer.officer_id, "OFF-0001")
        self.assertEqual(officer.department, "Sierra Leone Police")
        with self.assertRaises(ValueError):
            GovernmentOfficer("Ministry of Magic", "Bo")
        with self.assertRaises(ValueError):
            GovernmentOfficer("Sierra Leone Police", "Accra")

    def test_department_permissions(self) -> None:
        police = GovernmentOfficer("Sierra Leone Police", "Bo")
        ombudsman = GovernmentOfficer("Office of the Ombudsman", "Bo")
        self.assertFalse(police.can_handle(self.water))
        self.assertTrue(ombudsman.can_handle(self.water))
        with self.assertRaises(PermissionError):
            police.handle(self.water, "Under review")
        update = ombudsman.handle(self.water, "Under review", "Referred.", "2026-08-06")
        expected = StatusUpdate("Under review", date(2026, 8, 6), "OFF-0002", "Referred.")
        self.assertEqual(update, expected)
        self.assertEqual((police.updates_made, ombudsman.updates_made), (0, 1))

    def test_next_steps_static_method(self) -> None:
        self.assertEqual(GovernmentOfficer.next_steps("submitted"), ("Under review", "Rejected"))
        self.assertEqual(GovernmentOfficer.next_steps("Resolved"), ())
        with self.assertRaises(ValueError):
            GovernmentOfficer.next_steps("Lost")

    def test_handle_rejects_wrong_type(self) -> None:
        officer = GovernmentOfficer("Office of the Ombudsman", "Bo")
        with self.assertRaises(TypeError):
            officer.handle("CMP-0001", "Under review")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
