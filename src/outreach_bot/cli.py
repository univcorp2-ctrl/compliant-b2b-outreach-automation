import asyncio
from pathlib import Path

import typer
import uvicorn
from sqlmodel import Session

from outreach_bot.config import get_settings
from outreach_bot.crawler import CompliantCrawler, import_companies_csv
from outreach_bot.db import get_engine, init_db
from outreach_bot.models import Campaign
from outreach_bot.service import export_companies, run_campaign

app = typer.Typer(no_args_is_help=True, help="Compliance-first B2B outreach automation")


def _read_seeds(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


@app.command("init-db")
def init_database() -> None:
    init_db()
    typer.echo("Database initialized")


@app.command()
def crawl(seed: list[str] = typer.Option([], "--seed"), seed_file: Path | None = typer.Option(None, "--seed-file")) -> None:
    init_db()
    seeds = list(seed)
    if seed_file:
        seeds.extend(_read_seeds(seed_file))
    if not seeds:
        typer.echo("No seeds supplied; nothing to crawl")
        return
    with Session(get_engine()) as session:
        found = asyncio.run(CompliantCrawler(get_settings()).crawl(session, seeds))
    typer.echo(f"Discovered or updated {len(found)} companies")


@app.command("import-csv")
def import_csv(path: Path) -> None:
    init_db()
    with Session(get_engine()) as session:
        count = import_companies_csv(session, path)
    typer.echo(f"Imported {count} rows")


@app.command("create-campaign")
def create_campaign(name: str, subject: str, body_file: Path, channels: str = "email,form", daily_limit: int = 20) -> None:
    init_db()
    campaign = Campaign(name=name, subject_template=subject, body_template=body_file.read_text(encoding="utf-8"), channels=channels, daily_limit=daily_limit)
    with Session(get_engine()) as session:
        session.add(campaign)
        session.commit()
        session.refresh(campaign)
    typer.echo(f"Created campaign {campaign.id}; approval is still required")


@app.command("approve-campaign")
def approve_campaign(campaign_id: int) -> None:
    init_db()
    with Session(get_engine()) as session:
        campaign = session.get(Campaign, campaign_id)
        if campaign is None:
            raise typer.BadParameter("Campaign not found")
        campaign.approved = True
        session.add(campaign)
        session.commit()
    typer.echo(f"Approved campaign {campaign_id}")


@app.command("run-campaign")
def run_campaign_command(campaign_id: int, live: bool = False) -> None:
    init_db()
    with Session(get_engine()) as session:
        stats = asyncio.run(run_campaign(session, campaign_id, get_settings(), dry_run=not live))
    typer.echo(stats)


@app.command()
def export(path: Path = Path("exports/companies.csv")) -> None:
    init_db()
    with Session(get_engine()) as session:
        count = export_companies(session, path)
    typer.echo(f"Exported {count} companies to {path}")


@app.command()
def daily(seed_file: Path = Path("data/seeds.txt"), campaign_id: int | None = None, live: bool = False) -> None:
    init_db()
    seeds = _read_seeds(seed_file)
    with Session(get_engine()) as session:
        if seeds:
            asyncio.run(CompliantCrawler(get_settings()).crawl(session, seeds))
        export_companies(session, get_settings().exports_dir / "companies.csv")
        if campaign_id is not None:
            stats = asyncio.run(run_campaign(session, campaign_id, get_settings(), dry_run=not live))
            typer.echo(stats)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run("outreach_bot.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
