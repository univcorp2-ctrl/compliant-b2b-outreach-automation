# 初期設定・本番設定ガイド

## 1. ドライラン

```bash
cp .env.example .env
python -m pip install -e '.[dev]'
outreach-bot init-db
outreach-bot serve
```

`/docs`でFastAPIの操作画面を確認できます。

## 2. リスト入力

`data/seeds.txt`へ規約とrobots.txtを確認済みの公開一覧URLを1行ずつ記載します。

```bash
outreach-bot crawl --seed-file data/seeds.txt
outreach-bot export
```

CSVは `name,website_url,contact_email,contact_form_url,industry,prefecture` を推奨します。

```bash
outreach-bot import-csv companies.csv
```

## 3. SMTPと送信者

`.env`へ会社名、担当者、返信可能な送信元、停止受付先、SMTPを設定します。SMTPパスワードはコミットしません。SPF、DKIM、DMARCも設定してください。

## 4. フォーム許可リスト

```dotenv
OUTREACH_ALLOWED_FORM_DOMAINS=example.jp,partner.example.com
```

ワイルドカードではありません。CAPTCHAがあるページは自動スキップします。

## 5. キャンペーン

```bash
outreach-bot create-campaign "協業提案" "{company_name}様へのご相談" data/campaign-body.example.txt --channels email,form --daily-limit 20
outreach-bot approve-campaign 1
outreach-bot run-campaign 1
```

`artifacts/`のプレビューを確認後、実送信フラグを設定して `--live` を使います。

## 6. GitHub Actions

Variables: `OUTREACH_SENDER_NAME`、`OUTREACH_SENDER_EMAIL`、`OUTREACH_SENDER_COMPANY`、`OUTREACH_SENDER_PHONE`、`OUTREACH_OPT_OUT_EMAIL`、`OUTREACH_ALLOWED_FORM_DOMAINS`、`OUTREACH_DAILY_LIMIT`、`OUTREACH_LIVE_APPROVED`。

Secrets: `OUTREACH_SMTP_HOST`、`OUTREACH_SMTP_USERNAME`、`OUTREACH_SMTP_PASSWORD`。

実送信は手動workflowで`live=true`、かつ`OUTREACH_LIVE_APPROVED=true`のときだけ有効です。永続化対象は `data/`、`exports/`、`artifacts/` です。
