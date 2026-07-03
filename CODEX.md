# CODEX.md

## Project intent
This repository automates only compliant B2B discovery and outreach. Never add CAPTCHA bypass, stealth fingerprinting, unsolicited bulk-send logic, scraping behind authentication, or collection of sensitive/personal data.

## Required invariants
- Respect robots.txt and source-site terms.
- Keep dry-run as the default.
- Require campaign approval and explicit live-mode environment flags.
- Require an allowlist for contact-form submission.
- Apply suppression, refusal-text detection, idempotency, and daily/domain limits before delivery.
- Do not log secrets or message-body personal data.

## Quality gates
Run `ruff check .` and `pytest` before merging. Update README and docs when behavior or required secrets change.
