from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from outreach_bot.config import Settings
from outreach_bot.extract import canonical_domain, normalize_email
from outreach_bot.models import Campaign, Company, ConsentBasis, OutreachAttempt, Suppression


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


def idempotency_key(company_id: int, campaign_id: int, channel: str) -> str:
    return f"company:{company_id}:campaign:{campaign_id}:channel:{channel}"


def can_contact(session: Session, company: Company, campaign: Campaign, channel: str, settings: Settings) -> PolicyDecision:
    if not campaign.approved:
        return PolicyDecision(False, "campaign_not_approved")
    if not campaign.active or not company.active:
        return PolicyDecision(False, "inactive")
    if company.no_solicitation:
        return PolicyDecision(False, "no_solicitation_detected")
    if company.consent_basis == ConsentBasis.UNKNOWN:
        return PolicyDecision(False, "consent_basis_unknown")
    if channel == "email" and not company.contact_email:
        return PolicyDecision(False, "missing_email")
    if channel == "form" and not company.contact_form_url:
        return PolicyDecision(False, "missing_form")
    domain = canonical_domain(company.website_url)
    suppressed_values = {domain}
    if company.contact_email:
        suppressed_values.add(normalize_email(company.contact_email))
    if any(item.value.lower() in suppressed_values for item in session.exec(select(Suppression)).all()):
        return PolicyDecision(False, "suppressed")
    key = idempotency_key(company.id or 0, campaign.id or 0, channel)
    if session.exec(select(OutreachAttempt).where(OutreachAttempt.idempotency_key == key)).first():
        return PolicyDecision(False, "already_attempted")
    today = datetime.now(UTC).date()
    attempts_today = session.exec(select(OutreachAttempt).where(OutreachAttempt.campaign_id == campaign.id, OutreachAttempt.attempted_on == today, OutreachAttempt.status.in_(["sent", "submitted", "dry_run"]))).all()
    if len(attempts_today) >= min(campaign.daily_limit, settings.daily_limit):
        return PolicyDecision(False, "daily_limit_reached")
    same_domain_today = [attempt for attempt in attempts_today if canonical_domain(attempt.destination) == domain or attempt.destination.lower().endswith(f"@{domain}")]
    if len(same_domain_today) >= settings.per_domain_daily_limit:
        return PolicyDecision(False, "per_domain_limit_reached")
    if channel == "form" and domain not in settings.form_domain_allowlist:
        return PolicyDecision(False, "form_domain_not_allowlisted")
    return PolicyDecision(True, "allowed")
