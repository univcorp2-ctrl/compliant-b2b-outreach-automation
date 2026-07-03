from sqlmodel import Session, SQLModel, create_engine

from outreach_bot.config import Settings
from outreach_bot.models import Campaign, Company, Suppression
from outreach_bot.policy import can_contact


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_policy_requires_approval_and_honors_suppression():
    settings = Settings(allowed_form_domains="example.jp")
    with make_session() as session:
        company = Company(name="Example", canonical_domain="example.jp", website_url="https://example.jp", contact_email="info@example.jp", contact_form_url="https://example.jp/contact")
        campaign = Campaign(name="test", subject_template="Hi", body_template="Body")
        session.add(company)
        session.add(campaign)
        session.commit()
        session.refresh(company)
        session.refresh(campaign)
        assert can_contact(session, company, campaign, "email", settings).reason == "campaign_not_approved"
        campaign.approved = True
        session.add(campaign)
        session.commit()
        assert can_contact(session, company, campaign, "email", settings).allowed is True
        session.add(Suppression(kind="domain", value="example.jp"))
        session.commit()
        assert can_contact(session, company, campaign, "email", settings).reason == "suppressed"
