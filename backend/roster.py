"""Student directory, backed by the persistent DB.

A real deployment should sync this from the school's existing student
information system rather than auto-registering on first chat - the
auto-register fallback below is a placeholder until that integration
exists, and always assigns to the first counselor account found, which is
fine for a single-counselor pilot and not fine once there are several.
"""

from backend import db
from backend.models import Student


def get_or_register_student(student_id: str) -> Student:
    row = db.get_student(student_id)
    if row is not None:
        return Student(
            id=row["id"],
            display_name=row["display_name"],
            assigned_counselor_id=row["assigned_counselor_id"],
        )

    counselor_id = db.get_any_counselor_id()
    if counselor_id is None:
        raise RuntimeError(
            "No counselor accounts exist yet - create one with "
            "`python scripts/create_counselor.py` before students can chat."
        )

    db.create_student(id=student_id, display_name=student_id, assigned_counselor_id=counselor_id)
    return Student(
        id=student_id,
        display_name=student_id,
        assigned_counselor_id=counselor_id,
    )
