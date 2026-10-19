"""Domain models for the Citizen Complaint System (CCS).

Task 1 (OOP Basics): the classes ``Citizen``, ``Complaint`` and
``GovernmentOfficer`` model the real world. They interact: a citizen submits
a complaint, and an officer from the responsible department updates it.

Task 3 (Methods): the classes use instance methods, class methods
(``@classmethod``) and static methods (``@staticmethod``).

Privacy by design (DPG): citizens are identified only by a system-generated
code (e.g. CIT-0001). No names, phone numbers, national ID numbers or email
addresses are stored, and complaint text is checked so that phone numbers and
email addresses cannot be typed into it by accident.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, NamedTuple, Optional, Tuple, Union

DateInput = Union[date, str]  # a date object or text in YYYY-MM-DD format

# Reference data is stored in tuples because it must never change while the
# program runs (immutable).
DISTRICTS: Tuple[str, ...] = (
    "Bo", "Bombali", "Bonthe", "Falaba", "Kailahun", "Kambia", "Karene",
    "Kenema", "Koinadugu", "Kono", "Moyamba", "Port Loko", "Pujehun",
    "Tonkolili", "Western Area Rural", "Western Area Urban",
)
LANGUAGES: Tuple[str, ...] = ("English", "Krio", "Mende", "Temne", "Limba")
CATEGORIES: Tuple[str, ...] = (
    "Roads", "Water supply", "Electricity", "Waste collection",
    "Health services", "Education", "Security", "Corruption", "Other",
)
PRIORITIES: Tuple[str, ...] = ("Low", "Medium", "High", "Urgent")
STATUSES: Tuple[str, ...] = ("Submitted", "Under review", "In progress", "Resolved", "Rejected")
CLOSED_STATUSES: Tuple[str, ...] = ("Resolved", "Rejected")
# Reports in these categories hide who made them (whistleblower protection).
CONFIDENTIAL_CATEGORIES: Tuple[str, ...] = ("Corruption",)
OVERSIGHT_DEPARTMENT = "Office of the Ombudsman"

# The department responsible for each category of complaint.
DEPARTMENT_FOR_CATEGORY: Dict[str, str] = {
    "Roads": "Sierra Leone Roads Authority",
    "Water supply": "Ministry of Water Resources",
    "Electricity": "Electricity Distribution and Supply Authority",
    "Waste collection": "Local Council",
    "Health services": "Ministry of Health",
    "Education": "Ministry of Basic and Senior Secondary Education",
    "Security": "Sierra Leone Police",
    "Corruption": "Anti-Corruption Commission",
    "Other": OVERSIGHT_DEPARTMENT,
}
DEPARTMENTS: Tuple[str, ...] = tuple(sorted(set(DEPARTMENT_FOR_CATEGORY.values())))

# Which status may follow which. A closed complaint cannot change again.
ALLOWED_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "Submitted": ("Under review", "Rejected"),
    "Under review": ("In progress", "Resolved", "Rejected"),
    "In progress": ("Resolved",),
    "Resolved": (),
    "Rejected": (),
}

# Target number of days to close a complaint, by priority (service standard).
TARGET_DAYS: Dict[str, int] = {"Urgent": 3, "High": 7, "Medium": 14, "Low": 30}

FIRST_VALID_DATE = date(2000, 1, 1)


def match_option(value: str, options: Tuple[str, ...]) -> Optional[str]:
    """Return the option that matches ``value`` (ignoring case and extra
    spaces), or None."""
    cleaned = " ".join((value or "").split()).lower()
    for option in options:
        if option.lower() == cleaned:
            return option
    return None


def contains_personal_identifier(text: str) -> bool:
    """Detect text that looks like a phone number, ID number or email address.

    Seven or more digits in a row (after removing spaces, dashes, dots,
    brackets and plus signs) are treated as a phone or ID number.
    """
    compact = re.sub(r"[\s\-+().]", "", text or "")
    has_long_number = re.search(r"\d{7,}", compact) is not None
    has_email = re.search(r"\S+@\S+\.\S+", text or "") is not None
    return has_long_number or has_email


def parse_date(value: Optional[DateInput]) -> date:
    """Turn 'YYYY-MM-DD' text (or a date, or None for today) into a date,
    rejecting dates in the future or before 2000-01-01."""
    if value is None or value == "":
        return date.today()
    if isinstance(value, date):
        result = value
    else:
        try:
            result = date.fromisoformat(str(value).strip())
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format, e.g. 2026-03-15.") from None
    if not FIRST_VALID_DATE <= result <= date.today():
        raise ValueError("Date cannot be in the future or before 2000-01-01.")
    return result


# --------------------------------------------------------------------------- #
# Immutable record (tuple)
# --------------------------------------------------------------------------- #
class StatusUpdate(NamedTuple):
    """One change of status. Immutable, so the history of a complaint is a
    permanent audit trail that nobody can quietly rewrite."""

    status: str
    changed_on: date
    updated_by: str  # the officer's code, or "Citizen" for the first entry
    note: str


# --------------------------------------------------------------------------- #
# Citizen
# --------------------------------------------------------------------------- #
class Citizen:
    """A member of the public, identified by a pseudonymous code."""

    ID_PREFIX = "CIT"
    _next_number = 1  # class attribute shared by every Citizen object

    def __init__(self, district: str, language: str = "English") -> None:
        clean_district = match_option(district, DISTRICTS)
        if clean_district is None:
            raise ValueError(f"Unknown district: '{district}'.")
        clean_language = match_option(language, LANGUAGES)
        if clean_language is None:
            raise ValueError(f"Language must be one of: {', '.join(LANGUAGES)}.")

        # The ID is only created after every check has passed.
        self.citizen_id: str = Citizen.generate_id()
        self.district: str = clean_district
        self.language: str = clean_language
        self._complaint_ids: Tuple[str, ...] = ()

    # ---- class methods ---------------------------------------------------- #
    @classmethod
    def generate_id(cls) -> str:
        """Create the next unique citizen code, e.g. CIT-0001."""
        new_id = f"{cls.ID_PREFIX}-{cls._next_number:04d}"
        cls._next_number += 1
        return new_id

    @classmethod
    def reset_counter(cls) -> None:
        """Restart ID numbering (used by the automated tests)."""
        cls._next_number = 1

    @classmethod
    def from_tuple(cls, data: Tuple[str, str]) -> "Citizen":
        """Alternative constructor: build a Citizen from (district, language)."""
        district, language = data
        return cls(district, language)

    # ---- instance methods ------------------------------------------------- #
    @property
    def complaint_ids(self) -> Tuple[str, ...]:
        """Codes of the complaints this citizen has submitted (read-only)."""
        return self._complaint_ids

    def submit_complaint(
        self,
        category: str,
        description: str,
        priority: str = "Medium",
        district: Optional[str] = None,
        submitted_on: Optional[DateInput] = None,
    ) -> "Complaint":
        """Create a new complaint from this citizen and remember its code.

        ``district`` is where the problem is; it defaults to the citizen's
        own district.
        """
        complaint = Complaint(
            self, category, description, priority,
            district if district else self.district, submitted_on,
        )
        self._complaint_ids = self._complaint_ids + (complaint.complaint_id,)
        return complaint

    def update_record(
        self, district: Optional[str] = None, language: Optional[str] = None
    ) -> None:
        """Update district and/or language. All checks run before anything changes."""
        new_district, new_language = self.district, self.language
        if district is not None:
            new_district = match_option(district, DISTRICTS) or ""
            if not new_district:
                raise ValueError(f"Unknown district: '{district}'.")
        if language is not None:
            new_language = match_option(language, LANGUAGES) or ""
            if not new_language:
                raise ValueError(f"Language must be one of: {', '.join(LANGUAGES)}.")
        self.district, self.language = new_district, new_language

    def display_info(self, show_codes: bool = True) -> str:
        """Return a readable summary of the citizen.

        Staff views use ``show_codes=False`` so that a list of citizens never
        reveals who made which complaint (protecting confidential reports).
        """
        if show_codes:
            complaints = ", ".join(self._complaint_ids) if self._complaint_ids else "none yet"
        else:
            complaints = str(len(self._complaint_ids))
        return (
            f"Citizen {self.citizen_id} | {self.district} | Language: {self.language} | "
            f"Complaints: {complaints}"
        )

    def __repr__(self) -> str:
        return (
            f"Citizen(citizen_id={self.citizen_id!r}, district={self.district!r}, "
            f"language={self.language!r})"
        )


# --------------------------------------------------------------------------- #
# Complaint
# --------------------------------------------------------------------------- #
class Complaint:
    """A complaint about a public service, with its full status history."""

    ID_PREFIX = "CMP"
    MIN_DESCRIPTION = 10
    MAX_DESCRIPTION = 300
    MAX_NOTE = 200
    _next_number = 1

    def __init__(
        self,
        citizen: Citizen,
        category: str,
        description: str,
        priority: str = "Medium",
        district: Optional[str] = None,
        submitted_on: Optional[DateInput] = None,
    ) -> None:
        if not isinstance(citizen, Citizen):
            raise TypeError("citizen must be a Citizen object.")
        clean_category = match_option(category, CATEGORIES)
        if clean_category is None:
            raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")
        clean_priority = match_option(priority, PRIORITIES)
        if clean_priority is None:
            raise ValueError(f"Priority must be one of: {', '.join(PRIORITIES)}.")
        clean_district = match_option(district or citizen.district, DISTRICTS)
        if clean_district is None:
            raise ValueError(f"Unknown district: '{district}'.")
        clean_description = Complaint.validate_text(
            description, "Description", Complaint.MIN_DESCRIPTION, Complaint.MAX_DESCRIPTION
        )
        clean_date = parse_date(submitted_on)

        self.complaint_id: str = Complaint.generate_id()
        self.citizen: Citizen = citizen
        self.category: str = clean_category
        self.priority: str = clean_priority
        self.district: str = clean_district
        self.description: str = clean_description
        self.submitted_on: date = clean_date
        self._history: Tuple[StatusUpdate, ...] = (
            StatusUpdate("Submitted", clean_date, "Citizen", "Complaint received."),
        )

    # ---- class methods ---------------------------------------------------- #
    @classmethod
    def generate_id(cls) -> str:
        """Create the next unique complaint code, e.g. CMP-0001."""
        new_id = f"{cls.ID_PREFIX}-{cls._next_number:04d}"
        cls._next_number += 1
        return new_id

    @classmethod
    def reset_counter(cls) -> None:
        """Restart ID numbering (used by the automated tests)."""
        cls._next_number = 1

    @classmethod
    def categories(cls) -> str:
        """The complaint categories as one readable line."""
        return ", ".join(CATEGORIES)

    # ---- static methods --------------------------------------------------- #
    @staticmethod
    def validate_text(text: str, name: str, minimum: int, maximum: int) -> str:
        """Tidy spaces and check length and privacy rules for free text."""
        clean = " ".join((text or "").split())
        if not minimum <= len(clean) <= maximum:
            raise ValueError(f"{name} must be {minimum} to {maximum} characters long.")
        if contains_personal_identifier(clean):
            raise ValueError(
                f"For privacy, the {name.lower()} must not contain phone numbers, "
                "ID numbers or email addresses."
            )
        return clean

    @staticmethod
    def department_for(category: str) -> str:
        """The government department responsible for a category."""
        clean = match_option(category, CATEGORIES)
        if clean is None:
            raise ValueError(f"Unknown category: '{category}'.")
        return DEPARTMENT_FOR_CATEGORY[clean]

    # ---- instance methods ------------------------------------------------- #
    @property
    def history(self) -> Tuple[StatusUpdate, ...]:
        """Every status change, oldest first (read-only tuple)."""
        return self._history

    @property
    def status(self) -> str:
        """The current status is the most recent entry in the history."""
        return self._history[-1].status

    @property
    def department(self) -> str:
        """The department responsible for this complaint."""
        return Complaint.department_for(self.category)

    @property
    def is_confidential(self) -> bool:
        """True for categories where the reporter's identity is protected."""
        return self.category in CONFIDENTIAL_CATEGORIES

    def submitted_by(self) -> str:
        """The citizen code to show on screen, hidden for confidential reports."""
        return "(confidential)" if self.is_confidential else self.citizen.citizen_id

    def is_open(self) -> bool:
        """True until the complaint is resolved or rejected."""
        return self.status not in CLOSED_STATUSES

    def days_open(self, today: Optional[date] = None) -> int:
        """Days since submission (until closing, if the complaint is closed)."""
        end = self._history[-1].changed_on if not self.is_open() else (today or date.today())
        return (end - self.submitted_on).days

    def is_overdue(self, today: Optional[date] = None) -> bool:
        """True if still open after the target number of days for its priority."""
        return self.is_open() and self.days_open(today) > TARGET_DAYS[self.priority]

    def update_status(
        self,
        new_status: str,
        officer_id: str,
        note: str = "",
        changed_on: Optional[DateInput] = None,
    ) -> StatusUpdate:
        """Move the complaint to a new status, following the allowed workflow.

        A note explaining the outcome is required when resolving or rejecting.
        Normally called through ``GovernmentOfficer.handle``.
        """
        clean_status = match_option(new_status, STATUSES)
        if clean_status is None:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")
        allowed = ALLOWED_TRANSITIONS[self.status]
        if clean_status not in allowed:
            options = ", ".join(allowed) if allowed else "none (complaint is closed)"
            raise ValueError(
                f"Cannot change from '{self.status}' to '{clean_status}'. Allowed: {options}."
            )
        clean_note = " ".join((note or "").split())
        if clean_status in CLOSED_STATUSES and not clean_note:
            raise ValueError(
                f"A note explaining the outcome is required to mark it {clean_status}."
            )
        if clean_note:
            clean_note = Complaint.validate_text(clean_note, "Note", 5, Complaint.MAX_NOTE)
        when = parse_date(changed_on)
        if when < self._history[-1].changed_on:
            raise ValueError("A status update cannot be dated before the previous update.")

        update = StatusUpdate(clean_status, when, officer_id, clean_note)
        self._history = self._history + (update,)
        return update

    def display_info(self, include_history: bool = True) -> str:
        """Return a readable summary of the complaint."""
        overdue = " | OVERDUE" if self.is_overdue() else ""
        lines: Tuple[str, ...] = (
            f"Complaint {self.complaint_id} | {self.category} | {self.priority} priority | "
            f"{self.district} | Status: {self.status}{overdue}",
            f"   Submitted {self.submitted_on.isoformat()} by {self.submitted_by()} | "
            f"Responsible: {self.department}",
            f"   \"{self.description}\"",
        )
        if include_history:
            lines += tuple(
                f"   {u.changed_on.isoformat()}  {u.status:<13} "
                f"by {u.updated_by:<9} {u.note}".rstrip()
                for u in self._history
            )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"Complaint(complaint_id={self.complaint_id!r}, category={self.category!r}, "
            f"status={self.status!r}, district={self.district!r})"
        )


# --------------------------------------------------------------------------- #
# GovernmentOfficer
# --------------------------------------------------------------------------- #
class GovernmentOfficer:
    """A public officer who reviews and resolves complaints for a department."""

    ID_PREFIX = "OFF"
    _next_number = 1

    def __init__(self, department: str, district: str) -> None:
        clean_department = match_option(department, DEPARTMENTS)
        if clean_department is None:
            raise ValueError("Unknown department. Choose one from the list.")
        clean_district = match_option(district, DISTRICTS)
        if clean_district is None:
            raise ValueError(f"Unknown district: '{district}'.")

        self.officer_id: str = GovernmentOfficer.generate_id()
        self.department: str = clean_department
        self.district: str = clean_district
        self.updates_made: int = 0

    # ---- class methods ---------------------------------------------------- #
    @classmethod
    def generate_id(cls) -> str:
        """Create the next unique officer code, e.g. OFF-0001."""
        new_id = f"{cls.ID_PREFIX}-{cls._next_number:04d}"
        cls._next_number += 1
        return new_id

    @classmethod
    def reset_counter(cls) -> None:
        """Restart ID numbering (used by the automated tests)."""
        cls._next_number = 1

    # ---- static methods --------------------------------------------------- #
    @staticmethod
    def next_steps(status: str) -> Tuple[str, ...]:
        """Statuses that may follow the given status."""
        clean = match_option(status, STATUSES)
        if clean is None:
            raise ValueError(f"Unknown status: '{status}'.")
        return ALLOWED_TRANSITIONS[clean]

    # ---- instance methods ------------------------------------------------- #
    def can_handle(self, complaint: Complaint) -> bool:
        """Officers handle their own department's complaints; the Ombudsman
        provides oversight and can handle any complaint."""
        return self.department in (complaint.department, OVERSIGHT_DEPARTMENT)

    def handle(
        self, complaint: Complaint, new_status: str, note: str = "",
        changed_on: Optional[DateInput] = None,
    ) -> StatusUpdate:
        """Update a complaint's status on behalf of this officer.

        This is where the officer and complaint objects interact: the officer
        checks it is responsible, then the complaint records the change.
        """
        if not isinstance(complaint, Complaint):
            raise TypeError("complaint must be a Complaint object.")
        if not self.can_handle(complaint):
            raise PermissionError(
                f"{self.officer_id} ({self.department}) cannot handle {complaint.category} "
                f"complaints. They belong to {complaint.department}."
            )
        update = complaint.update_status(new_status, self.officer_id, note, changed_on)
        self.updates_made += 1
        return update

    def display_info(self) -> str:
        """Return a readable summary of the officer."""
        return (
            f"Officer {self.officer_id} | {self.department} | {self.district} | "
            f"Updates made: {self.updates_made}"
        )

    def __repr__(self) -> str:
        return (
            f"GovernmentOfficer(officer_id={self.officer_id!r}, "
            f"department={self.department!r}, district={self.district!r})"
        )
