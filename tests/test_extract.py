from outreach_bot.extract import canonical_domain, extract_contact, extract_links


def test_extract_contact_and_refusal():
    html = """
    <html><head><title>株式会社サンプル｜公式</title></head>
    <body>
      <p>営業目的のお問い合わせはご遠慮ください。</p>
      <a href="mailto:info@example.jp">mail</a>
      <a href="/contact">お問い合わせ</a>
      <a href="https://partner.example.com/">partner</a>
    </body></html>
    """
    result = extract_contact(html, "https://www.example.jp/about")
    assert result.name == "株式会社サンプル"
    assert result.emails == ["info@example.jp"]
    assert result.contact_form_url == "https://www.example.jp/contact"
    assert result.no_solicitation is True
    assert canonical_domain("https://www.EXAMPLE.jp/a") == "example.jp"
    assert extract_links(html, "https://www.example.jp/about", same_domain_only=False) == [
        "https://partner.example.com/"
    ]
