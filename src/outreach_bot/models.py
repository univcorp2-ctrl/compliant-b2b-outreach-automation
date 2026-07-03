from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class ConsentBasis(StrEnum):
    OPT_IN = "opt_in"
    EXISTING_RELATIONSHIP = "existing_relationship"
    PUBLISHED_BUSINESS_CONTACT = "published_business_contact"
    UNKNOWN = "unknown"


class Company(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    canonical_domain: str = Field(index=True, unique=True)
    website_url: str
    source_url: str | None = None
    industry: str | None = None
    prefecture: str | None = None
    contact_email: str | None = Field(default=None, index=True)
    contact_phone: str | None = None
    contact_form_url: str | None = None
    consent_basis: ConsentBasis = ConsentBasis.PUBLISHED_BUSINESS_CONTACT
    no_solicitation: bool = False
    no_solicitation_evidence: str | None = None
    active: bool = True
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class Campaign(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    subject_template: str
    body_template: str
    channels: str = "email,form"
    daily_limit: int = 20
    approved: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class OutreachAttempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    campaign_id: int = Field(foreign_key="campaign.id", index=True)
    channel: str
    destination: str
    status: str = Field(index=True)
    reason: str | None = None
    idempotency_key: str = Field(index=True, unique=True)
    attempted_on: date = Field(default_factory=lambda: datetime.now(UTC).date(), index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Suppression(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    value: str = Field(index=True)
    reason: str = "opt_out"
    created_at: datetime = Field(default_factory=utcnow)
