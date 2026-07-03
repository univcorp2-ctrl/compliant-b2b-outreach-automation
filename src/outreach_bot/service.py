import csv
from pathlib import Path

from sqlmodel import Session, select

from outreach_bot.config import Settings
from outreach_bot.forms import submit_contact_form
from outreach_bot.mailer import render_template, send_email
from outreach_bot.models import Campaign, Company, OutreachAttempt
from outreach_bot.policy import can_contact, idempotency_key


async def run_campaign(
    session: Session,
    campaign_id: int,
    settings: Settings,
    *,
    dry_run: bool = True,
) -> dict[str, int]:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError(f"Campaign {campaign_id} not found")
    stats = {"sent": 0, "submitted": 0, "dry_run": 0, "skipped": 0, "failed": 0}
    channels = [value.strip() for value in campaign.channels.split(",") if value.strip()]
    companies = session.exec(select(Company).where(Company.active == True)).all()  # noqa: E712

    for company in companies:
        for channel in channels:
            decision = can_contact(session, company, campaign, channel, settings)
            if not decision.allowed:
                stats["skipped"] += 1
                continue
            destination = company.contact_email if channel == "email" else company.contact_form_url
            assert destination is not None
            key = idempotency_key(company.id or 0, campaign.id or 0, channel)
            try:
                if channel == "email":
                    status = send_email(company, campaign, settings, dry_run=dry_run)
                    reason = None
                elif channel == "form":
                    subject = render_template(campaign.subject_template, company, settings)
                    body = render_template(campaign.body_template, company, settings)
                    result = await submit_contact_form(
                        company, subject, body, settings, dry_run=dry_run
                    )
                    status, reason = result.status, result.reason
                else:
                    status, reason = "skipped", "unsupported_channel"
            except Exception as exc:  # deliberate job-level isolation
                status, reason = "failed", f"{type(exc).__name__}: {exc}"

            attempt = OutreachAttempt(
                company_id=company.id or 0,
                campaign_id=campaign.id or 0,
                channel=channel,
                destination=destination,
                status=status,
                reason=reason,
                idempotency_key=key,
            )
            session.add(attempt)
            session.commit()
            stats[status if status in stats else "failed"] += 1
    return stats


def export_companies(session: Session, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    companies = session.exec(select(Company)).all()
    fields = [
        "name",
        "canonical_domain",
        "website_url",
        "source_url",
        "industry",
        "prefecture",
        "contact_email",
        "contact_phone",
        "contact_form_url",
        "consent_basis",
        "no_solicitation",
        "last_seen_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for company in companies:
            writer.writerow({field: getattr(company, field) for field in fields})
    return len(companies)
