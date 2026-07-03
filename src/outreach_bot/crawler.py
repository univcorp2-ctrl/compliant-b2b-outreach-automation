import asyncio
import csv
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit

import httpx
from sqlmodel import Session, select

from outreach_bot.config import Settings
from outreach_bot.extract import canonical_domain, extract_contact, extract_links
from outreach_bot.models import Company


class CompliantCrawler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    async def _robots_allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = robotparser.RobotFileParser()
            parser.set_url(f"{root}/robots.txt")
            try:
                response = await client.get(parser.url)
                parser.parse(response.text.splitlines() if response.status_code < 400 else [])
            except httpx.HTTPError:
                parser.parse([])
            self._robots[root] = parser
        return self._robots[root].can_fetch(self.settings.user_agent, url)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        if not await self._robots_allowed(client, url):
            return None
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        if "text/html" not in response.headers.get("content-type", ""):
            return None
        return response.text

    async def discover_domains(self, seed_urls: list[str]) -> list[tuple[str, str]]:
        discovered: dict[str, tuple[str, str]] = {}
        async with httpx.AsyncClient(headers={"User-Agent": self.settings.user_agent}, timeout=self.settings.request_timeout_seconds, follow_redirects=True) as client:
            for seed in seed_urls:
                html = await self._fetch(client, seed)
                if html is None:
                    continue
                seed_domain = canonical_domain(seed)
                discovered.setdefault(seed_domain, (seed, seed))
                for url in extract_links(html, seed, same_domain_only=False):
                    domain = canonical_domain(url)
                    if domain and domain not in discovered:
                        parts = urlsplit(url)
                        discovered[domain] = (f"{parts.scheme}://{parts.netloc}/", seed)
                    if len(discovered) >= self.settings.max_discovered_domains_per_seed:
                        break
                await asyncio.sleep(self.settings.crawl_delay_seconds)
        return list(discovered.values())

    async def crawl_company(self, homepage: str, source_url: str) -> Company | None:
        domain = canonical_domain(homepage)
        if not domain:
            return None
        queue = deque([homepage])
        visited: set[str] = set()
        best = None
        async with httpx.AsyncClient(headers={"User-Agent": self.settings.user_agent}, timeout=self.settings.request_timeout_seconds, follow_redirects=True) as client:
            while queue and len(visited) < self.settings.max_pages_per_domain:
                url = queue.popleft()
                if url in visited or canonical_domain(url) != domain:
                    continue
                visited.add(url)
                html = await self._fetch(client, url)
                if html is None:
                    continue
                discovery = extract_contact(html, url)
                if best is None or len(discovery.emails) + bool(discovery.contact_form_url) > len(best.emails) + bool(best.contact_form_url):
                    best = discovery
                if discovery.no_solicitation:
                    best = discovery
                    break
                for link in extract_links(html, url, same_domain_only=True):
                    lower = link.lower()
                    if any(word in lower for word in ("contact", "inquiry", "company", "about", "profile")):
                        queue.appendleft(link)
                    elif len(queue) < self.settings.max_pages_per_domain:
                        queue.append(link)
                await asyncio.sleep(self.settings.crawl_delay_seconds)
        if best is None:
            return None
        return Company(name=best.name, canonical_domain=domain, website_url=homepage, source_url=source_url, contact_email=best.emails[0] if best.emails else None, contact_phone=best.phones[0] if best.phones else None, contact_form_url=best.contact_form_url, no_solicitation=best.no_solicitation, no_solicitation_evidence=best.no_solicitation_evidence)

    async def crawl(self, session: Session, seed_urls: list[str]) -> list[Company]:
        targets = await self.discover_domains(seed_urls)
        results: list[Company] = []
        for homepage, source_url in targets:
            found = await self.crawl_company(homepage, source_url)
            if found is None:
                continue
            existing = session.exec(select(Company).where(Company.canonical_domain == found.canonical_domain)).first()
            if existing:
                for field in ("name", "website_url", "source_url", "contact_email", "contact_phone", "contact_form_url", "no_solicitation", "no_solicitation_evidence"):
                    value = getattr(found, field)
                    if value not in (None, "", False):
                        setattr(existing, field, value)
                existing.last_seen_at = datetime.now(UTC)
                session.add(existing)
                results.append(existing)
            else:
                session.add(found)
                results.append(found)
            session.commit()
        return results


def import_companies_csv(session: Session, path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            website = (row.get("website_url") or row.get("website") or "").strip()
            if not website:
                continue
            domain = canonical_domain(website)
            existing = session.exec(select(Company).where(Company.canonical_domain == domain)).first()
            company = existing or Company(name=(row.get("name") or domain).strip(), canonical_domain=domain, website_url=website)
            company.contact_email = (row.get("contact_email") or row.get("email") or "").strip() or None
            company.contact_form_url = (row.get("contact_form_url") or "").strip() or None
            company.contact_phone = (row.get("contact_phone") or row.get("phone") or "").strip() or None
            company.industry = (row.get("industry") or "").strip() or None
            company.prefecture = (row.get("prefecture") or "").strip() or None
            session.add(company)
            session.commit()
            count += 1
    return count
