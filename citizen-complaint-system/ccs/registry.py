"""The ComplaintRegistry: where all citizens, officers and complaints are stored.

Task 2 (Python Data Structures): the chosen data structure is the
**dictionary**. Objects are stored with their unique code as the key, e.g.
``{"CMP-0001": <Complaint>, "CMP-0002": <Complaint>}``, so a citizen can track
any complaint instantly by its code. Tuples (optional bonus) are used for data
that must not change, such as status histories and report rows.

The simple functions ``add_record`` and ``display_records`` at the bottom of
this module add and display records from the dictionary.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple, Union

from ccs.models import Citizen, Complaint, GovernmentOfficer

CountRow = Tuple[str, int]
Record = Union[Citizen, GovernmentOfficer, Complaint]


class ComplaintRegistry:
    """Stores citizens, officers and complaints in dictionaries keyed by code."""

    REPORT_FIELDS: Tuple[str, ...] = ("category", "status", "district", "priority")
    EXPORT_COLUMNS: Tuple[str, ...] = (
        "district", "category", "total", "open", "resolved", "rejected",
    )

    def __init__(self) -> None:
        self._citizens: Dict[str, Citizen] = {}
        self._officers: Dict[str, GovernmentOfficer] = {}
        self._complaints: Dict[str, Complaint] = {}

    # ---- adding records --------------------------------------------------- #
    def add_citizen(self, citizen: Citizen) -> Citizen:
        """Store a citizen under its citizen_id."""
        if not isinstance(citizen, Citizen):
            raise TypeError("Only Citizen objects can be added as citizens.")
        if citizen.citizen_id in self._citizens:
            raise ValueError(f"Citizen {citizen.citizen_id} is already registered.")
        self._citizens[citizen.citizen_id] = citizen
        return citizen

    def add_officer(self, officer: GovernmentOfficer) -> GovernmentOfficer:
        """Store an officer under its officer_id."""
        if not isinstance(officer, GovernmentOfficer):
            raise TypeError("Only GovernmentOfficer objects can be added as officers.")
        if officer.officer_id in self._officers:
            raise ValueError(f"Officer {officer.officer_id} is already registered.")
        self._officers[officer.officer_id] = officer
        return officer

    def add_complaint(self, complaint: Complaint) -> Complaint:
        """Store a complaint. The citizen who made it must already be registered."""
        if not isinstance(complaint, Complaint):
            raise TypeError("Only Complaint objects can be added as complaints.")
        if complaint.complaint_id in self._complaints:
            raise ValueError(f"Complaint {complaint.complaint_id} is already registered.")
        if complaint.citizen.citizen_id not in self._citizens:
            citizen_id = complaint.citizen.citizen_id
            raise ValueError(f"Register citizen {citizen_id} before adding their complaint.")
        self._complaints[complaint.complaint_id] = complaint
        return complaint

    # ---- looking records up ----------------------------------------------- #
    @staticmethod
    def _key(code: str) -> str:
        return (code or "").strip().upper()

    def get_citizen(self, citizen_id: str) -> Optional[Citizen]:
        """Return the citizen with this code (case-insensitive), or None."""
        return self._citizens.get(ComplaintRegistry._key(citizen_id))

    def get_officer(self, officer_id: str) -> Optional[GovernmentOfficer]:
        """Return the officer with this code (case-insensitive), or None."""
        return self._officers.get(ComplaintRegistry._key(officer_id))

    def get_complaint(self, complaint_id: str) -> Optional[Complaint]:
        """Return the complaint with this code (case-insensitive), or None."""
        return self._complaints.get(ComplaintRegistry._key(complaint_id))

    def citizens(self) -> Tuple[Citizen, ...]:
        return tuple(self._citizens.values())

    def officers(self) -> Tuple[GovernmentOfficer, ...]:
        return tuple(self._officers.values())

    def complaints(self) -> Tuple[Complaint, ...]:
        return tuple(self._complaints.values())

    def __len__(self) -> int:
        return len(self._complaints)

    def __contains__(self, code: object) -> bool:
        if not isinstance(code, str):
            return False
        key = ComplaintRegistry._key(code)
        return key in self._complaints or key in self._citizens or key in self._officers

    def __iter__(self) -> Iterator[Complaint]:
        """Looping over the registry loops over its complaints."""
        return iter(self._complaints.values())

    # ---- displaying records ----------------------------------------------- #
    def display_citizens(self) -> str:
        if not self._citizens:
            return "No citizens registered yet."
        return "\n".join(c.display_info(show_codes=False) for c in self._citizens.values())

    def display_officers(self) -> str:
        if not self._officers:
            return "No officers registered yet."
        return "\n".join(o.display_info() for o in self._officers.values())

    def display_complaints(self, include_history: bool = True) -> str:
        if not self._complaints:
            return "No complaints submitted yet."
        separator = "\n\n" if include_history else "\n"
        return separator.join(c.display_info(include_history) for c in self._complaints.values())

    # ---- analysis --------------------------------------------------------- #
    def open_complaints(self) -> Tuple[Complaint, ...]:
        """Complaints that are not yet resolved or rejected."""
        return tuple(c for c in self._complaints.values() if c.is_open())

    def overdue_complaints(self, today: Optional[date] = None) -> Tuple[Complaint, ...]:
        """Open complaints past their target time, oldest first."""
        overdue = (c for c in self._complaints.values() if c.is_overdue(today))
        return tuple(sorted(overdue, key=lambda c: c.submitted_on))

    def count_by(self, field: str) -> Tuple[CountRow, ...]:
        """Number of complaints for each value of a field, most common first.

        ``field`` must be one of REPORT_FIELDS: category, status, district, priority.
        """
        if field not in ComplaintRegistry.REPORT_FIELDS:
            fields = ", ".join(ComplaintRegistry.REPORT_FIELDS)
            raise ValueError(f"Field must be one of: {fields}.")
        counts: Dict[str, int] = {}
        for complaint in self._complaints.values():
            value = getattr(complaint, field)
            counts[value] = counts.get(value, 0) + 1
        return tuple(sorted(counts.items(), key=lambda row: (-row[1], row[0])))

    def resolution_rate(self) -> float:
        """Percentage of all complaints that have been resolved (0 if none)."""
        if not self._complaints:
            return 0.0
        resolved = sum(1 for c in self._complaints.values() if c.status == "Resolved")
        return round(100 * resolved / len(self._complaints), 1)

    def average_days_to_resolve(self) -> Optional[float]:
        """Average days from submission to resolution, or None if none resolved."""
        days = tuple(c.days_open() for c in self._complaints.values() if c.status == "Resolved")
        return round(sum(days) / len(days), 1) if days else None

    def complaints_for_department(self, department: str) -> Tuple[Complaint, ...]:
        """All complaints a given department is responsible for."""
        return tuple(c for c in self._complaints.values() if c.department == department)

    @staticmethod
    def format_counts(rows: Tuple[CountRow, ...], label: str) -> str:
        """Turn (label, count) rows into an aligned text table."""
        if not rows:
            return "No complaints recorded yet."
        total = sum(count for _, count in rows)
        header = f"{label:<22}{'Complaints':>12}{'Share':>8}"
        divider = "-" * len(header)
        body = tuple(f"{name:<22}{count:>12}{count / total:>8.0%}" for name, count in rows)
        return "\n".join((header, divider) + body + (divider, f"{'Total':<22}{total:>12}"))

    # ---- public statistics export (DPG: open data, transparency) ---------- #
    def export_public_statistics(self, path: Union[str, Path]) -> int:
        """Write complaint totals by district and category to a CSV file.

        The file supports government transparency. It contains only counts:
        no citizen codes, descriptions, notes or dates. Returns rows written.
        """
        totals: Dict[Tuple[str, str], Tuple[int, int, int, int]] = {}
        for c in self._complaints.values():
            total, open_, resolved, rejected = totals.get((c.district, c.category), (0, 0, 0, 0))
            totals[(c.district, c.category)] = (
                total + 1,
                open_ + (1 if c.is_open() else 0),
                resolved + (1 if c.status == "Resolved" else 0),
                rejected + (1 if c.status == "Rejected" else 0),
            )
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(ComplaintRegistry.EXPORT_COLUMNS)
            for (district, category), counts in sorted(totals.items()):
                writer.writerow((district, category) + counts)
        return len(totals)

    # ---- alternative constructor ------------------------------------------ #
    @classmethod
    def with_sample_data(cls) -> "ComplaintRegistry":
        """Create a registry pre-filled with fictional demonstration data."""
        registry = cls()
        citizens = tuple(
            registry.add_citizen(Citizen.from_tuple(data))
            for data in (
                ("Western Area Urban", "Krio"), ("Bo", "Mende"), ("Port Loko", "Temne"),
                ("Kenema", "English"), ("Bombali", "Limba"), ("Western Area Urban", "English"),
            )
        )
        officers = tuple(
            registry.add_officer(GovernmentOfficer(dept, district))
            for dept, district in (
                ("Sierra Leone Roads Authority", "Western Area Urban"),
                ("Electricity Distribution and Supply Authority", "Bo"),
                ("Local Council", "Western Area Urban"),
                ("Office of the Ombudsman", "Western Area Urban"),
            )
        )
        # (citizen, category, priority, date, description, ((officer, status, date, note), ...))
        data = (
            (0, "Roads", "High", "2026-06-02",
             "Large potholes on the main road near the market make it unsafe for vehicles.",
             ((0, "Under review", "2026-06-04", "Site inspection scheduled."),
              (0, "In progress", "2026-06-10", "Repair crew assigned."),
              (0, "Resolved", "2026-06-15", "Potholes filled and road resurfaced."))),
            (1, "Electricity", "Urgent", "2026-07-01",
             "Fallen power line across the junction since last night's storm.",
             ((1, "Under review", "2026-07-01", "Emergency team informed."),
              (1, "Resolved", "2026-07-02", "Line removed and power restored."))),
            (0, "Waste collection", "Medium", "2026-07-20",
             "Rubbish has not been collected from our street for three weeks.",
             ((2, "Under review", "2026-07-22", ""),
              (2, "In progress", "2026-07-25", "Collection added to next week's route."))),
            (2, "Water supply", "High", "2026-08-03",
             "The community water point has been broken for two weeks.",
             ((3, "Under review", "2026-08-06", "Referred to the water directorate."),)),
            (3, "Health services", "Medium", "2026-08-12",
             "The health centre was closed during its posted opening hours on Monday.",
             ()),
            (4, "Corruption", "High", "2026-08-18",
             "Staff asked for an unofficial payment before issuing a public service form.",
             ((3, "Under review", "2026-08-20", "Forwarded for confidential investigation."),)),
            (5, "Roads", "Low", "2026-09-01",
             "Street sign at the roundabout is missing, which confuses drivers.",
             ((0, "Rejected", "2026-09-03", "Duplicate of an existing work order."),)),
            (1, "Electricity", "Medium", "2026-09-10",
             "Street lights on our road have not worked for a month.",
             ()),
            (5, "Waste collection", "High", "2026-09-15",
             "Blocked drain is overflowing with waste and causing flooding.",
             ((2, "Under review", "2026-09-16", ""),
              (2, "In progress", "2026-09-18", "Drain clearing team assigned."),
              (2, "Resolved", "2026-09-22", "Drain cleared and waste removed."))),
            (3, "Education", "Low", "2026-09-28",
             "School does not display its fees publicly as required.",
             ()),
        )
        for c_index, category, priority, when, text, updates in data:
            complaint = registry.add_complaint(
                citizens[c_index].submit_complaint(category, text, priority, submitted_on=when)
            )
            for o_index, status, changed, note in updates:
                officers[o_index].handle(complaint, status, note, changed)
        return registry


# --------------------------------------------------------------------------- #
# Simple functions to add and display records (Task 2)
# --------------------------------------------------------------------------- #
def add_record(registry: ComplaintRegistry, record: Record) -> str:
    """Add a Citizen, GovernmentOfficer or Complaint to the dictionary; return its code."""
    if isinstance(record, Citizen):
        return registry.add_citizen(record).citizen_id
    if isinstance(record, GovernmentOfficer):
        return registry.add_officer(record).officer_id
    if isinstance(record, Complaint):
        return registry.add_complaint(record).complaint_id
    raise TypeError("Record must be a Citizen, GovernmentOfficer or Complaint.")


def display_records(registry: ComplaintRegistry) -> None:
    """Loop through the dictionaries and print every record."""
    print("=== Citizens ===")
    print(registry.display_citizens())
    print()
    print("=== Government Officers ===")
    print(registry.display_officers())
    print()
    print("=== Complaints ===")
    print(registry.display_complaints())

