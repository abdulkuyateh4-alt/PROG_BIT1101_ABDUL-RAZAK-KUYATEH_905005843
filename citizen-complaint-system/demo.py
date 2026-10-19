"""Guided demonstration of every assignment requirement.

Run with:  python demo.py

This script needs no keyboard input, so it produces the same sample output
every time. It is the quickest way for a marker to see Tasks 1, 2 and 3.
All citizens, officers and complaints shown are fictional.
"""

from __future__ import annotations

from datetime import date

from ccs import (
    Citizen,
    Complaint,
    ComplaintRegistry,
    GovernmentOfficer,
    add_record,
    display_records,
)

REPORT_DATE = date(2026, 10, 19)  # fixed date so the overdue list is always the same


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    # ------------------------------------------------------------------ #
    section("TASK 1 - Classes, attributes, objects and their interaction")
    # ------------------------------------------------------------------ #
    citizen = Citizen("Western Area Urban", "krio")             # object creation
    officer = GovernmentOfficer("Sierra Leone Roads Authority", "Western Area Urban")
    print("Created:", citizen)
    print("Created:", officer)

    print("\nInteraction 1: the citizen submits a complaint.")
    complaint = citizen.submit_complaint(
        "Roads", "Large potholes on the main road near the market make it unsafe.",
        "High", submitted_on="2026-06-02",
    )
    print("Created:", complaint)
    print(citizen.display_info())

    print("\nInteraction 2: the officer from the responsible department updates it.")
    officer.handle(complaint, "Under review", "Site inspection scheduled.", "2026-06-04")
    officer.handle(complaint, "In progress", "Repair crew assigned.", "2026-06-10")
    officer.handle(complaint, "Resolved", "Potholes filled and road resurfaced.", "2026-06-15")
    print(complaint.display_info())
    print(officer.display_info())

    citizen.update_record(language="English")
    print("\nAfter update_record(language='English'):", citizen.display_info())

    # ------------------------------------------------------------------ #
    section("TASK 2 - Data structure: a dictionary keyed by unique code")
    # ------------------------------------------------------------------ #
    registry = ComplaintRegistry()
    for record in (citizen, officer, complaint):
        print(f"add_record() stored {add_record(registry, record)}")   # simple add function
    print(f"\nDictionary look-up by key: registry.get_complaint('cmp-0001') -> "
          f"{registry.get_complaint('cmp-0001')!r}")
    print("\nLooping through the dictionary with display_records():\n")
    display_records(registry)                                        # simple display function

    print("\nOptional tuples: the status history is a tuple of immutable NamedTuples:")
    first = complaint.history[0]
    print(f"   {first!r}")
    status, changed_on, updated_by, note = complaint.history[-1]    # tuple unpacking
    print(f"   Latest -> {status} on {changed_on} by {updated_by}: {note}")
    try:
        first.status = "Resolved"  # type: ignore[misc]
    except AttributeError:
        print("   Attempt to rewrite the history was blocked (tuples are immutable).")

    # ------------------------------------------------------------------ #
    section("TASK 3 - Instance, class and static methods")
    # ------------------------------------------------------------------ #
    print("Instance method  complaint.days_open()        ->", complaint.days_open(), "days")
    print("Instance method  officer.can_handle(complaint) ->", officer.can_handle(complaint))
    print("Class method     Complaint.categories()       ->", Complaint.categories())
    print("Class method     Citizen.from_tuple(('Bo','Mende')) ->",
          Citizen.from_tuple(("Bo", "Mende")))
    print("Static method    Complaint.department_for('Electricity') ->",
          Complaint.department_for("Electricity"))
    print("Static method    GovernmentOfficer.next_steps('Submitted') ->",
          GovernmentOfficer.next_steps("Submitted"))

    # ------------------------------------------------------------------ #
    section("DPG - Privacy protection, workflow rules and validation")
    # ------------------------------------------------------------------ #
    police = GovernmentOfficer("Sierra Leone Police", "Bo")
    second = citizen.submit_complaint("Water supply", "Water point broken for two weeks.",
                                      submitted_on="2026-08-03")
    pending = citizen.submit_complaint("Roads", "Missing street sign at the roundabout.",
                                       "Low", submitted_on="2026-09-01")
    checks = (
        ("description with a phone number", lambda: citizen.submit_complaint(
            "Roads", "Call me on 076 123 456 about the road.")),
        ("description with an email address", lambda: citizen.submit_complaint(
            "Roads", "Reply to me at someone@example.com please.")),
        ("updating a resolved complaint", lambda: officer.handle(
            complaint, "In progress", "Reopening.")),
        ("rejecting without a note", lambda: officer.handle(pending, "Rejected")),
        ("skipping straight from Submitted to Resolved", lambda: officer.handle(
            pending, "Resolved", "Sign replaced.")),
        ("police officer handling a water complaint", lambda: police.handle(
            second, "Under review")),
        ("unknown district", lambda: Citizen("Lagos")),
    )
    for label, action in checks:
        try:
            action()
        except (ValueError, PermissionError) as error:
            print(f"Rejected {label}: {error}")

    # ------------------------------------------------------------------ #
    section("Reports with the full (fictional) sample data set")
    # ------------------------------------------------------------------ #
    for cls in (Citizen, Complaint, GovernmentOfficer):
        cls.reset_counter()
    sample = ComplaintRegistry.with_sample_data()                     # class method constructor
    print(ComplaintRegistry.format_counts(sample.count_by("category"), "Category"))
    print(f"\nResolution rate: {sample.resolution_rate()}% | "
          f"Average days to resolve: {sample.average_days_to_resolve()}")
    print(f"\nOverdue on {REPORT_DATE.isoformat()}:")
    for c in sample.overdue_complaints(REPORT_DATE):
        print(f"   {c.complaint_id} {c.category:<16} {c.priority:<6} "
              f"open {c.days_open(REPORT_DATE)} days")
    print("\nConfidential corruption report as staff see it:")
    report = sample.get_complaint("CMP-0006")
    if report is not None:
        print(report.display_info(include_history=False))
    rows = sample.export_public_statistics("public_complaint_statistics.csv")
    print(f"\nExported {rows} rows of totals to public_complaint_statistics.csv")


if __name__ == "__main__":
    main()
