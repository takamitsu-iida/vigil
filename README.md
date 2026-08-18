# Vigil

Pythonで実装した軽量なインシデント管理システムです。

> [!NOTE]
>
> vigilは「寝ずの番」「徹夜の見張り」という意味を持つ名詞です。

---

## スクリーンショット

| インシデント一覧 | インシデント詳細 |
|---|---|
| *(screenshot)* | *(screenshot)* |

---

## クイックスタート

### Docker Compose（推奨）

```bash
cp .env.example .env          # 必要に応じて編集
docker compose up -d
```

ブラウザで http://localhost:8000 を開く。

### ローカル起動

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 必要に応じて編集
uvicorn vigil.main:app --reload
```

ブラウザで http://localhost:8000 を開く。

---

## 環境変数

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/incident.db` | SQLite DB パス |
| `SLACK_WEBHOOK_URL` | *(空)* | Slack Incoming Webhook URL（省略可） |
| `DISCORD_WEBHOOK_URL` | *(空)* | Discord Webhook URL（省略可） |
| `ESCALATION_TIMEOUT_MINUTES` | `10` | 未応答時にエスカレーションするまでの分数 |

<br>

> [!NOTE]
>
> DiscordのWebhook作成方法（PCのブラウザで操作）
>
> - サーバーを作成します
> - そのサーバーの設定を開いて「連携サービス」を開きます
> - 「ウェブフックを作成」というボタンをクリックします

<br>

---

## API エンドポイント

### アラート

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/api/v1/alerts` | アラートを受信してインシデントを発火 |

### インシデント

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/api/v1/incidents` | 一覧取得（`status` / `limit` / `offset` フィルタ対応） |
| `GET` | `/api/v1/incidents/{id}` | 詳細取得 |
| `POST` | `/api/v1/incidents/{id}/acknowledge` | 承認（Acknowledge） |
| `POST` | `/api/v1/incidents/{id}/resolve` | 解決（Resolve） |

### ユーザー

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/api/v1/users` | ユーザー作成 |
| `GET` | `/api/v1/users` | ユーザー一覧 |

### スケジュール

| メソッド | パス | 説明 |
|---|---|---|
| `PUT` | `/api/v1/schedules/{team_name}/oncall` | オンコール担当者の設定・切り替え |

対話型ドキュメント: http://localhost:8000/docs
