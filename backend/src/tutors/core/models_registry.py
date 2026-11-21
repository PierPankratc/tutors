"""Central SQLAlchemy metadata registry for Alembic autogenerate & migrations."""

from tutors.core.database import Base
from tutors.modules.audit.models import AuditLog
from tutors.modules.auth_users.models import User, UserRole
from tutors.modules.profiles.models import (
    ContactRequest,
    ContactRequestStatus,
    StudentProfile,
    Subject,
    TutorProfile,
    TutorProfileStatus,
    TutorSubject,
)
from tutors.modules.reviews.models import Review
from tutors.modules.verification.models import VerificationDocument, VerificationStatus

__all__ = [
    "AuditLog",
    "Base",
    "ContactRequest",
    "ContactRequestStatus",
    "Review",
    "StudentProfile",
    "Subject",
    "TutorProfile",
    "TutorProfileStatus",
    "TutorSubject",
    "User",
    "UserRole",
    "VerificationDocument",
    "VerificationStatus",
]
