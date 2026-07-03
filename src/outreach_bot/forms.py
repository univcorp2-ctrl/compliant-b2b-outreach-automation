from dataclasses import dataclass

from playwright.async_api import Page, async_playwright

from outreach_bot.config import Settings
from outreach_bot.extract import NO_SOLICITATION_PATTERNS, canonical_domain
from outreach_bot.models import Company

CAPTCHA_MARKERS = ("recaptcha", "hcaptcha", "cf-turnstile", "captcha")


@dataclass(slots=True)
class FormResult:
    status: str
    reason: str | None = None
    artifact: str | None = None


async def _fill_first(page: Page, selectors: tuple[str, ...], value: str) -> bool:
    if not value:
        return False
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count() and await locator.is_visible():
            await locator.fill(value)
            return True
    return False


async def submit_contact_form(company: Company, subject: str, message: str, settings: Settings, *, dry_run: bool) -> FormResult:
    if not company.contact_form_url:
        return FormResult("skipped", "missing_form")
    domain = canonical_domain(company.contact_form_url)
    if domain not in settings.form_domain_allowlist:
        return FormResult("skipped", "form_domain_not_allowlisted")
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if dry_run or not settings.live_forms:
        artifact = settings.artifacts_dir / f"form-{company.canonical_domain}.txt"
        artifact.write_text(f"URL: {company.contact_form_url}\nSUBJECT: {subject}\nMESSAGE:\n{message}\n", encoding="utf-8")
        return FormResult("dry_run", artifact=str(artifact))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(company.contact_form_url, wait_until="domcontentloaded", timeout=45_000)
            html = (await page.content()).lower()
            visible_text = await page.locator("body").inner_text()
            if any(marker in html for marker in CAPTCHA_MARKERS):
                return FormResult("skipped", "captcha_detected")
            if any(pattern in visible_text for pattern in NO_SOLICITATION_PATTERNS):
                return FormResult("skipped", "no_solicitation_detected")
            await _fill_first(page, ('input[name*="company" i]', 'input[name*="corp" i]', 'input[placeholder*="会社"]'), settings.sender_company)
            await _fill_first(page, ('input[name*="name" i]', 'input[placeholder*="氏名"]', 'input[placeholder*="お名前"]'), settings.sender_name)
            await _fill_first(page, ('input[type="email"]', 'input[name*="mail" i]'), settings.sender_email)
            await _fill_first(page, ('input[type="tel"]', 'input[name*="phone" i]', 'input[name*="tel" i]'), settings.sender_phone)
            await _fill_first(page, ('input[name*="subject" i]', 'input[placeholder*="件名"]'), subject)
            filled_message = await _fill_first(page, ('textarea[name*="message" i]', 'textarea[name*="body" i]', "textarea"), message)
            if not filled_message:
                return FormResult("skipped", "message_field_not_found")
            screenshot = settings.artifacts_dir / f"form-before-submit-{company.canonical_domain}.png"
            await page.screenshot(path=str(screenshot), full_page=True)
            submit = page.locator('button[type="submit"], input[type="submit"]').first
            if not await submit.count():
                return FormResult("skipped", "submit_button_not_found", str(screenshot))
            await submit.click()
            await page.wait_for_timeout(2500)
            return FormResult("submitted", artifact=str(screenshot))
        finally:
            await browser.close()
