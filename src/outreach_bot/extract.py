import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}")
NO_SOLICITATION_PATTERNS = (
    "営業メールお断り",
    "営業目的のお問い合わせはご遠慮",
    "営業・セールスはお断り",
    "セールス目的の利用を禁止",
    "売り込みはお断り",
    "営業連絡は受け付けておりません",
    "広告宣伝メールを拒否",
)
CONTACT_WORDS = ("お問い合わせ", "問合せ", "contact", "inquiry", "ご相談")
IGNORED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "google.com",
    "yahoo.co.jp",
    "line.me",
}


@dataclass(slots=True)
class ContactDiscovery:
    name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    contact_form_url: str | None = None
    no_solicitation: bool = False
    no_solicitation_evidence: str | None = None


def canonical_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def normalize_email(value: str) -> str:
    return value.strip().lower().removeprefix("mailto:").split("?", 1)[0]


def _extract_jsonld_name(soup: BeautifulSoup) -> str | None:
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.string or "{}")
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") in {"Organization", "Corporation", "LocalBusiness", "RealEstateAgent"}:
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return None


def extract_contact(html: str, page_url: str) -> ContactDiscovery:
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    og_name = soup.select_one('meta[property="og:site_name"]')
    name = (
        _extract_jsonld_name(soup)
        or (og_name.get("content", "").strip() if og_name else "")
        or title.split("|")[0].split("｜")[0].strip()
        or canonical_domain(page_url)
    )

    emails = {normalize_email(value) for value in EMAIL_RE.findall(visible_text)}
    for anchor in soup.select('a[href^="mailto:"]'):
        emails.add(normalize_email(anchor.get("href", "")))
    emails = {
        email
        for email in emails
        if email and not email.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"))
    }

    phones = {re.sub(r"\s+", "", phone) for phone in PHONE_RE.findall(visible_text)}
    form_url = None
    for form in soup.find_all("form"):
        if form.find("textarea") or form.find("input", {"type": "email"}):
            form_url = urljoin(page_url, form.get("action") or page_url)
            break
    if not form_url:
        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True).lower()
            if any(word.lower() in label for word in CONTACT_WORDS):
                form_url = urljoin(page_url, anchor["href"])
                break

    evidence = next((pattern for pattern in NO_SOLICITATION_PATTERNS if pattern in visible_text), None)
    return ContactDiscovery(
        name=name,
        emails=sorted(emails),
        phones=sorted(phones),
        contact_form_url=form_url,
        no_solicitation=evidence is not None,
        no_solicitation_evidence=evidence,
    )


def extract_links(html: str, base_url: str, *, same_domain_only: bool | None = None) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = canonical_domain(base_url)
    links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, anchor["href"]).split("#", 1)[0]
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            continue
        domain = canonical_domain(url)
        if not domain or any(domain == ignored or domain.endswith(f".{ignored}") for ignored in IGNORED_DOMAINS):
            continue
        if same_domain_only is True and domain != base_domain:
            continue
        if same_domain_only is False and domain == base_domain:
            continue
        links.add(url)
    return sorted(links)
