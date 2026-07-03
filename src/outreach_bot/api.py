from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from outreach_bot.config import get_settings
from outreach_bot.crawler import CompliantCrawler
from outreach_bot.db import get_session, init_db
from outreach_bot.models import Campaign, Company, Suppression
from outreach_bot.service import export_companies, run_campaign

app = FastAPI(title="Compliant B2B Outreach Automation", version="0.1.0")


class CrawlRequest(BaseModel):
    seeds: list[str] = Field(min_length=1, max_length=100)


class CampaignRequest(BaseModel):
    name: str
    subject_template: str
    body_template: str
    channels: str = "email,form"
    daily_limit: int = Field(default=20, ge=1, le=500)


class SuppressionRequest(BaseModel):
    kind: str
    value: str
    reason: str = "opt_out"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "compliance-first"}


@app.get("/companies", response_model=list[Company])
def companies(session: Session = Depends(get_session)):
    return session.exec(select(Company)).all()


@app.post("/crawl")
async def crawl(payload: CrawlRequest, session: Session = Depends(get_session)):
    crawler = CompliantCrawler(get_settings())
    found = await crawler.crawl(session, payload.seeds)
    return {"discovered": len(found)}


@app.post("/campaigns", response_model=Campaign)
def create_campaign(payload: CampaignRequest, session: Session = Depends(get_session)):
    campaign = Campaign(**payload.model_dump())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@app.post("/campaigns/{campaign_id}/approve", response_model=Campaign)
def approve_campaign(campaign_id: int, session: Session = Depends(get_session)):
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    campaign.approved = True
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@app.post("/campaigns/{campaign_id}/run")
async def execute_campaign(
    campaign_id: int,
    dry_run: bool = True,
    session: Session = Depends(get_session),
):
    try:
        return await run_campaign(session, campaign_id, get_settings(), dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/suppressions", response_model=Suppression)
def suppress(payload: SuppressionRequest, session: Session = Depends(get_session)):
    item = Suppression(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.post("/exports/companies")
def export(session: Session = Depends(get_session)):
    path = get_settings().exports_dir / "companies.csv"
    count = export_companies(session, Path(path))
    return {"count": count, "path": str(path)}
