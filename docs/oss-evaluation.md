# OSS調査・選定結果

調査日: 2026-07-03

標準構成は **HTTPX + Beautiful Soup + Playwright + FastAPI + SQLModel** です。小規模から開始でき、抽出・判定・送信のルールを監査しやすく、任意サイトに対するAIエージェントの誤送信を避けられるためです。

| OSS | 主用途 | 評価 | 今回の扱い |
|---|---|---|---|
| Scrapy | 大規模クロール | スケジューラ、重複排除、パイプライン、robots対応 | 大規模化時の第一候補 |
| scrapy-playwright | JSページ収集 | ScrapyへPlaywrightを統合 | Scrapy移行時に採用候補 |
| Playwright Python | ブラウザ自動化 | 決定論的セレクタと主要ブラウザ対応 | フォーム入力に採用 |
| Crawl4AI | LLM向け抽出 | Markdown化・LLM抽出に強い | 企業要約の拡張候補 |
| n8n | 業務連携 | SaaS連携が豊富 | CRM/Slack/Sheets連携候補 |
| Mautic | マーケティング自動化 | 許諾済みリードの育成に強い | opt-in後段候補 |
| listmonk | メール配信 | 高性能セルフホスト配信 | 許諾済み配信候補 |
| browser-use | AIブラウザ | 柔軟だが非決定的で誤送信リスク | 標準不採用 |
| Playwright MCP | LLMブラウザ操作 | 管理者支援に有効 | 将来候補 |

公式プロジェクト: `github.com/scrapy/scrapy`、`github.com/scrapy-plugins/scrapy-playwright`、`github.com/microsoft/playwright-python`、`github.com/microsoft/playwright-mcp`、`github.com/unclecode/crawl4ai`、`github.com/n8n-io/n8n`、`github.com/mautic/mautic`、`github.com/knadh/listmonk`、`github.com/browser-use/browser-use`。

## 推奨ロードマップ

- 数千社: 現構成とSQLite永続ボリューム
- 数万社: Scrapy + PostgreSQL + Redis + ワーカーキュー
- 許諾済み育成: Mautic/listmonkへ分離同期
- 業務連携: n8nを追加し、送信可否の最終判定は本APIに残す
