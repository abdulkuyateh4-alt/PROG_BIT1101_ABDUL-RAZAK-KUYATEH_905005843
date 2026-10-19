"""Citizen Complaint System (CCS).

An open-source, privacy-respecting tool that lets citizens in Sierra Leone
report problems with public services and follow them until they are fixed,
built with Object-Oriented Programming in Python.
"""

from ccs.models import (
    CATEGORIES,
    DEPARTMENTS,
    DISTRICTS,
    LANGUAGES,
    PRIORITIES,
    STATUSES,
    Citizen,
    Complaint,
    GovernmentOfficer,
    StatusUpdate,
)
from ccs.registry import ComplaintRegistry, add_record, display_records

__all__ = (
    "CATEGORIES",
    "DEPARTMENTS",
    "DISTRICTS",
    "LANGUAGES",
    "PRIORITIES",
    "STATUSES",
    "Citizen",
    "Complaint",
    "ComplaintRegistry",
    "GovernmentOfficer",
    "StatusUpdate",
    "add_record",
    "display_records",
)

__version__ = "1.0.0"
