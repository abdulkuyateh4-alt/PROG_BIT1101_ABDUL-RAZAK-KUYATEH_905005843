"""Citizen Complaint System - interactive command-line program.

Run with:  python main.py

Accessibility choices (DPG: inclusive design):
  * plain-language, numbered menus that work with screen readers;
  * no colours or symbols are needed to understand any message;
  * options can be chosen by number or by name, and text is case-insensitive;
  * citizens can record their preferred language (English, Krio, Mende,
    Temne or Limba) so officers can reply in that language;
  * runs offline on any computer with Python 3.8+ and no extra packages.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional, Tuple, TypeVar

from ccs import (
    CATEGORIES,
    DEPARTMENTS,
    DISTRICTS,
    LANGUAGES,
    PRIORITIES,
    Citizen,
    Complaint,
    ComplaintRegistry,
    GovernmentOfficer,
    add_record,
    display_records,
)
from ccs.models import TARGET_DAYS, match_option

APP_TITLE = "CITIZEN COMPLAINT SYSTEM (CCS) - Sierra Leone"
EXPORT_FILE = "public_complaint_statistics.csv"
T = TypeVar("T")

MENU: Tuple[Tuple[str, str], ...] = (
    ("1", "Register as a citizen"),
    ("2", "Submit a complaint"),
    ("3", "Track a complaint"),
    ("4", "Register a government officer"),
    ("5", "Update a complaint (officers)"),
    ("6", "View all records"),
    ("7", "Open and overdue complaints"),
    ("8", "Reports and statistics"),
    ("9", "Export public statistics (CSV)"),
    ("10", "Load sample data"),
    ("0", "Exit"),
)


class UserExit(Exception):
    """Raised when the user closes input (Ctrl+D / Ctrl+Z) or presses Ctrl+C."""


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def ask(prompt: str) -> str:
    """Read one line of input, turning Ctrl+C / end-of-input into UserExit."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise UserExit from None


def ask_until_valid(prompt: str, convert: Callable[[str], T], attempts: int = 3) -> Optional[T]:
    """Ask repeatedly until ``convert`` accepts the answer.

    Returns the converted value, or None after too many invalid attempts so
    the user is never trapped in a loop.
    """
    for attempt in range(1, attempts + 1):
        answer = ask(prompt)
        try:
            return convert(answer)
        except ValueError as error:
            remaining = attempts - attempt
            hint = f" ({remaining} attempt(s) left)" if remaining else ""
            print(f"  Error: {error}{hint}")
    print("  Too many invalid attempts. Returning to the main menu.")
    return None


def choose_from(
    options: Tuple[str, ...], name: str, default: Optional[str] = None
) -> Callable[[str], str]:
    """Build a converter that accepts an option by number or name.

    If ``default`` is given, pressing Enter selects it.
    """

    def convert(text: str) -> str:
        if not text and default is not None:
            return default
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1]
        matched = match_option(text, options)
        if matched is None:
            raise ValueError(f"{name} not recognised. Type its number or its name.")
        return matched

    return convert


def show_options(options: Tuple[str, ...], width: int = 28) -> None:
    """Print options numbered from 1, in columns."""
    per_line = 3 if width <= 28 else 2
    cells = tuple(f"{i:>2}. {option}" for i, option in enumerate(options, start=1))
    for start in range(0, len(cells), per_line):
        row = "".join(f"{cell:<{width}}" for cell in cells[start:start + per_line])
        print("   " + row.rstrip())


def show_heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def find(lookup: Callable[[str], Optional[T]], example: str, kind: str) -> Callable[[str], T]:
    """Build a converter that finds a record by code or explains the format."""

    def convert(text: str) -> T:
        record = lookup(text)
        if record is None:
            raise ValueError(f"No {kind} with that code (example: {example}).")
        return record

    return convert


# --------------------------------------------------------------------------- #
# Menu actions
# --------------------------------------------------------------------------- #
def register_citizen(registry: ComplaintRegistry) -> None:
    show_heading("Register as a citizen")
    print("Privacy notice: we do not collect your name, phone number or ID number.")
    print("Keep the citizen code shown at the end; you need it to submit complaints.")
    show_options(DISTRICTS)
    district = ask_until_valid(
        "Your district (number or name): ", choose_from(DISTRICTS, "District")
    )
    if district is None:
        return
    show_options(LANGUAGES)
    language = ask_until_valid("Preferred language (press Enter for English): ",
                               choose_from(LANGUAGES, "Language", default="English"))
    if language is None:
        return
    citizen = Citizen(district, language)
    add_record(registry, citizen)
    print(f"Success: you are registered with citizen code {citizen.citizen_id}.")


def submit_complaint(registry: ComplaintRegistry) -> None:
    show_heading("Submit a complaint")
    if not registry.citizens():
        print("Please register as a citizen first (option 1).")
        return
    citizen = ask_until_valid(
        "Your citizen code: ", find(registry.get_citizen, "CIT-0001", "citizen")
    )
    if citizen is None:
        return
    show_options(CATEGORIES)
    category = ask_until_valid("What is the problem about? (number or name): ",
                               choose_from(CATEGORIES, "Category"))
    if category is None:
        return
    if category == "Corruption":
        print("Note: corruption reports are confidential. Your code is hidden from staff lists.")
    district = ask_until_valid(
        f"District where the problem is (press Enter for {citizen.district}): ",
        choose_from(DISTRICTS, "District", default=citizen.district),
    )
    if district is None:
        return
    show_options(PRIORITIES)
    priority = ask_until_valid("How urgent is it? (press Enter for Medium): ",
                               choose_from(PRIORITIES, "Priority", default="Medium"))
    if priority is None:
        return
    low, high = Complaint.MIN_DESCRIPTION, Complaint.MAX_DESCRIPTION
    print(f"Describe the problem in {low}-{high} characters.")
    print("Do not include names, phone numbers or email addresses.")
    description = ask_until_valid(
        "Description: ",
        lambda t: Complaint.validate_text(t, "Description", Complaint.MIN_DESCRIPTION,
                                          Complaint.MAX_DESCRIPTION),
    )
    if description is None:
        return
    complaint = citizen.submit_complaint(category, description, priority, district)
    add_record(registry, complaint)
    print(f"Success: complaint {complaint.complaint_id} submitted.")
    print(f"It has been sent to: {complaint.department}.")
    print(f"Target response time for {priority} priority: {TARGET_DAYS[priority]} days.")
    print("Use option 3 with your complaint code to track progress.")


def track_complaint(registry: ComplaintRegistry) -> None:
    show_heading("Track a complaint")
    complaint = registry.get_complaint(ask("Complaint code: "))
    if complaint is None:
        print("No complaint with that code.")
        return
    print(complaint.display_info())
    if complaint.is_open():
        print(f"Open for {complaint.days_open()} day(s); target is "
              f"{TARGET_DAYS[complaint.priority]} day(s).")


def register_officer(registry: ComplaintRegistry) -> None:
    show_heading("Register a government officer")
    show_options(DEPARTMENTS, width=50)
    department = ask_until_valid("Department (number or name): ",
                                 choose_from(DEPARTMENTS, "Department"))
    if department is None:
        return
    show_options(DISTRICTS)
    district = ask_until_valid(
        "Office district (number or name): ", choose_from(DISTRICTS, "District")
    )
    if district is None:
        return
    officer = GovernmentOfficer(department, district)
    add_record(registry, officer)
    print(f"Success: officer registered with staff code {officer.officer_id}.")


def update_complaint(registry: ComplaintRegistry) -> None:
    show_heading("Update a complaint (officers)")
    if not registry.officers() or len(registry) == 0:
        print("This needs at least one officer (option 4) and one complaint (option 2).")
        return
    officer = ask_until_valid(
        "Your staff code: ", find(registry.get_officer, "OFF-0001", "officer")
    )
    if officer is None:
        return

    def to_complaint(text: str) -> Complaint:
        complaint = find(registry.get_complaint, "CMP-0001", "complaint")(text)
        if not officer.can_handle(complaint):
            raise ValueError(f"This complaint belongs to {complaint.department}.")
        if not complaint.is_open():
            raise ValueError(f"This complaint is already {complaint.status.lower()}.")
        return complaint

    complaint = ask_until_valid("Complaint code: ", to_complaint)
    if complaint is None:
        return
    print(complaint.display_info())
    steps = GovernmentOfficer.next_steps(complaint.status)
    show_options(steps)
    new_status = ask_until_valid("New status (number or name): ", choose_from(steps, "Status"))
    if new_status is None:
        return
    needs_note = new_status in ("Resolved", "Rejected")
    prompt = (
        "Note explaining the outcome (required): "
        if needs_note
        else "Note (optional, press Enter to skip): "
    )
    for _ in range(3):
        note = ask(prompt)
        try:
            update = officer.handle(complaint, new_status, note)
        except ValueError as error:
            print(f"  Error: {error}")
            continue
        print(f"Success: {complaint.complaint_id} is now '{update.status}'.")
        return
    print("  Too many invalid attempts. Returning to the main menu.")


def open_and_overdue(registry: ComplaintRegistry) -> None:
    show_heading("Open and overdue complaints")
    open_items = registry.open_complaints()
    if not open_items:
        print("There are no open complaints.")
        return
    overdue_ids = tuple(c.complaint_id for c in registry.overdue_complaints())
    for c in open_items:
        flag = "  OVERDUE" if c.complaint_id in overdue_ids else ""
        print(f"{c.complaint_id} | {c.category:<16} | {c.priority:<6} | {c.status:<12} | "
              f"{c.days_open():>3} days{flag}")
    print(f"Open: {len(open_items)} | Overdue: {len(overdue_ids)}")


def reports(registry: ComplaintRegistry) -> None:
    show_heading("Reports and statistics")
    if len(registry) == 0:
        print("No complaints recorded yet.")
        return
    for field, label in (("category", "Category"), ("status", "Status")):
        print(ComplaintRegistry.format_counts(registry.count_by(field), label))
        print()
    average = registry.average_days_to_resolve()
    print(f"Resolution rate: {registry.resolution_rate():.1f}% of all complaints")
    print("Average days to resolve: " + (f"{average:.1f}" if average is not None else "n/a"))


def export_statistics(registry: ComplaintRegistry) -> None:
    show_heading("Export public statistics")
    try:
        rows = registry.export_public_statistics(EXPORT_FILE)
    except OSError as error:
        print(f"  Error: could not write the file ({error}).")
        return
    print(f"Success: {rows} row(s) written to '{EXPORT_FILE}'.")
    print("The file contains only totals: no citizen codes, descriptions or notes.")


def load_sample(registry: ComplaintRegistry) -> ComplaintRegistry:
    show_heading("Load sample data")
    if registry.citizens() or registry.officers():
        answer = ask("This replaces the current data. Continue? (y/n): ").lower()
        if answer not in ("y", "yes"):
            print("Cancelled. Your data has not changed.")
            return registry
    for cls in (Citizen, Complaint, GovernmentOfficer):
        cls.reset_counter()
    sample = ComplaintRegistry.with_sample_data()
    print(f"Loaded {len(sample.citizens())} citizens, {len(sample.officers())} officers and "
          f"{len(sample)} complaints (all fictional).")
    return sample


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def print_menu() -> None:
    print()
    print("=" * len(APP_TITLE))
    print(APP_TITLE)
    print("=" * len(APP_TITLE))
    for key, label in MENU:
        print(f"  {key:>2}. {label}")


def run() -> int:
    registry = ComplaintRegistry()
    actions = {
        "1": register_citizen, "2": submit_complaint, "3": track_complaint,
        "4": register_officer, "5": update_complaint, "7": open_and_overdue,
        "8": reports, "9": export_statistics,
    }
    print("Welcome! Type the number of an option and press Enter.")
    try:
        while True:
            print_menu()
            choice = ask("Choose an option (0-10): ")
            if choice in actions:
                actions[choice](registry)
            elif choice == "6":
                show_heading("All records")
                display_records(registry)
            elif choice == "10":
                registry = load_sample(registry)
            elif choice == "0":
                print("Goodbye. Thank you for using CCS.")
                return 0
            else:
                print("  Error: please type a number from 0 to 10.")
    except UserExit:
        print("\nInput closed. Goodbye.")
        return 0


if __name__ == "__main__":
    sys.exit(run())
