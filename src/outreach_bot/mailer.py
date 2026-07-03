import smtplib
from email.message import EmailMessage
from pathlib import Path

from outreach_bot.config import Settings
from outreach_bot.models import Campaign, Company


def render_template(template: str, company: Company, settings: Settings) -> str:
    values = {
        "company_name": company.name,
        "website_url": company.website_url,
        "sender_name": settings.sender_name,
        "sender_company": settings.sender_company,
        "sender_email": settings.sender_email,
        "sender_phone": settings.sender_phone,
        "opt_out_email": settings.opt_out_email,
    }
    return template.format_map(values)


def build_email(company: Company, campaign: Campaign, settings: Settings) -> EmailMessage:
    if not company.contact_email:
        raise ValueError("Company has no contact email")
    message = EmailMessage()
    message["From"] = f"{settings.sender_name} <{settings.sender_email}>"
    message["To"] = company.contact_email
    message["Subject"] = render_template(campaign.subject_template, company, settings)
    message["List-Unsubscribe"] = f"<mailto:{settings.opt_out_email}?subject=unsubscribe>"
    body = render_template(campaign.body_template, company, settings)
    footer = (
        f"\n\n---\n送信者: {settings.sender_company} {settings.sender_name}\n"
        f"今後のご案内が不要な場合は {settings.opt_out_email} へご連絡ください。"
    )
    message.set_content(body + footer)
    return message


def send_email(
    company: Company,
    campaign: Campaign,
    settings: Settings,
    *,
    dry_run: bool,
) -> str:
    message = build_email(company, campaign, settings)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if dry_run or not settings.live_email:
        target = settings.artifacts_dir / f"email-{company.canonical_domain}.eml"
        target.write_bytes(bytes(message))
        return "dry_run"
    if not settings.smtp_host:
        raise RuntimeError("OUTREACH_SMTP_HOST is required for live email")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        if settings.smtp_starttls:
            client.starttls()
        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
    return "sent"
