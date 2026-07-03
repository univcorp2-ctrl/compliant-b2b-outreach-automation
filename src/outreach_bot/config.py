from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="OUTREACH_", case_sensitive=False, extra="ignore"
    )

    database_url: str = "sqlite:///data/outreach.db"
    user_agent: str = "CompliantB2BOutreachBot/0.1 (+contact: operator@example.com)"
    request_timeout_seconds: float = 20.0
    crawl_delay_seconds: float = 2.0
    max_pages_per_domain: int = 12
    max_discovered_domains_per_seed: int = 50
    daily_limit: int = 20
    per_domain_daily_limit: int = 1

    sender_name: str = "営業担当"
    sender_email: str = "operator@example.com"
    sender_company: str = "自社名"
    sender_phone: str = ""
    opt_out_email: str = "operator@example.com"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    live_email: bool = False
    live_forms: bool = False
    allowed_form_domains: str = ""
    artifacts_dir: Path = Path("artifacts")
    exports_dir: Path = Path("exports")

    @property
    def form_domain_allowlist(self) -> set[str]:
        return {
            value.strip().lower()
            for value in self.allowed_form_domains.split(",")
            if value.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
