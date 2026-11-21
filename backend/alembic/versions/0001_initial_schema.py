"""Initial 152-FZ compliant schema with PostgreSQL 16 GIN indexes and append-only audit_log.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    user_role_enum = postgresql.ENUM(
        "guest",
        "student",
        "tutor",
        "moderator",
        "admin",
        name="user_role_enum",
        create_type=False,
    )
    tutor_status_enum = postgresql.ENUM(
        "draft",
        "pending_moderation",
        "published",
        "suspended",
        name="tutor_profile_status_enum",
        create_type=False,
    )
    contact_status_enum = postgresql.ENUM(
        "pending",
        "accepted",
        "rejected",
        name="contact_request_status_enum",
        create_type=False,
    )
    verification_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="verification_status_enum",
        create_type=False,
    )

    for enum_type in (
        user_role_enum,
        tutor_status_enum,
        contact_status_enum,
        verification_status_enum,
    ):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_blind_index", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("is_totp_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pdn_consent_given_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("email_blind_index", name="uq_users_email_blind_index"),
    )
    op.create_index("ix_users_email_blind_index", "users", ["email_blind_index"], unique=True)

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("slug", name="uq_subjects_slug"),
        sa.UniqueConstraint("name", name="uq_subjects_name"),
    )
    op.create_index("ix_subjects_slug", "subjects", ["slug"], unique=True)
    op.execute("CREATE INDEX ix_subjects_name_trgm_gin ON subjects USING gin (name gin_trgm_ops)")

    op.create_table(
        "tutor_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("bio", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("experience", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "is_high_education", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("status", tutor_status_enum, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("contact_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('russian', coalesce(display_name, '')), 'A') || "
                "setweight(to_tsvector('russian', coalesce(bio, '')), 'B')",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.CheckConstraint("price >= 0", name="ck_tutor_profiles_price_non_negative"),
        sa.CheckConstraint(
            "experience >= 0 AND experience <= 80", name="ck_tutor_profiles_experience_bounds"
        ),
    )
    op.create_index("ix_tutor_profiles_status", "tutor_profiles", ["status"])
    op.create_index(
        "ix_tutor_profiles_search_vector_gin",
        "tutor_profiles",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_tutor_profiles_bio_trgm_gin ON tutor_profiles USING gin (bio gin_trgm_ops)"
    )
    op.create_table(
        "student_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("contact_encrypted", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "grade IS NULL OR (grade >= 1 AND grade <= 11)",
            name="ck_student_profiles_grade_bounds",
        ),
    )

    op.create_table(
        "tutor_subjects",
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )

    op.create_table(
        "contact_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "status", contact_status_enum, server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "tutor_id", name="uq_contact_request_student_tutor"),
    )
    op.create_index("ix_contact_requests_student_id", "contact_requests", ["student_id"])
    op.create_index("ix_contact_requests_tutor_id", "contact_requests", ["tutor_id"])
    op.create_table(
        "verification_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "status", verification_status_enum, server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("s3_key", name="uq_verification_documents_s3_key"),
    )
    op.create_index("ix_verification_documents_tutor_id", "verification_documents", ["tutor_id"])
    op.create_index("ix_verification_documents_status", "verification_documents", ["status"])

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_1_to_5"),
        sa.UniqueConstraint("student_id", "tutor_id", name="uq_review_student_tutor"),
    )
    op.create_index("ix_reviews_student_id", "reviews", ["student_id"])
    op.create_index("ix_reviews_tutor_id", "reviews", ["tutor_id"])
    op.create_index("ix_reviews_is_published", "reviews", ["is_published"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_entity_lookup", "audit_log", ["entity", "entity_id"])
    op.create_index("ix_audit_log_actor_created", "audit_log", ["actor_id", "created_at"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is strictly append-only: % operation is forbidden', TG_OP;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")

    for table in (
        "audit_log",
        "reviews",
        "verification_documents",
        "contact_requests",
        "tutor_subjects",
        "student_profiles",
        "tutor_profiles",
        "subjects",
        "users",
    ):
        op.drop_table(table)

    for enum_name in (
        "verification_status_enum",
        "contact_request_status_enum",
        "tutor_profile_status_enum",
        "user_role_enum",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
