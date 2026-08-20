# Vigil

Pythonで実装した軽量なインシデント管理システムです。

<br><br>

> [!NOTE]
>
> Vigilは「寝ずの番」「徹夜の見張り」という意味を持つ名詞です。

<br><br>

---

## スクリーンショット

| インシデント一覧 | インシデント詳細 |
|---|---|
| *(screenshot)* | *(screenshot)* |


<br><br>

---

<br><br>

## クイックスタート

### Docker Compose（推奨）

dockerで起動します。

```bash
make up
```

次にブラウザで http://localhost:8000 を開いてインシデント管理画面を表示します。

#### 停止

dockerを停止します。

```bash
make down
```

#### バージョンアップ

Github から pull した場合です。

```bash
make update
```

#### イメージ削除

```bash
make clean
```


### ローカル起動の場合（非推奨）

dockerを使わない場合の起動方法です。

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 必要に応じて編集
uvicorn vigil.main:app --reload
```

ブラウザで http://localhost:8000 を開きます。


> [!NOTE]
>
>  データベースに破壊的な変更がかかるバージョンアップの場合は以下の処理が必要になることがあります。
>
> ```bash
> rm data/incident.db
> alembic upgrade head
> ```

<br><br>

---

<br><br>

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

## ユーザーズガイド

Vigilの基本的な使い方をステップごとに説明します。

### 全体の流れ

```
1. ユーザーを登録する
2. オンコール担当者を設定する
3. （任意）エスカレーションポリシーを設定する
4. アラートを送信する → インシデント発火・通知
5. インシデントを承認・解決する
```

<br><br>

---

<br><br>

### ステップ1: ユーザーを登録する

通知を受け取るメンバーをあらかじめ登録します。
`discord_webhook_url` または `slack_webhook_url` を設定すると、そのユーザーに直接通知が届きます。

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice",
    "email": "alice@example.com",
    "discord_webhook_url": "https://discord.com/api/webhooks/..."
  }'
```

レスポンスに含まれる `id` は以降の手順で使います。

---

### ステップ2: オンコール担当者を設定する

チームのオンコール担当者を設定します。インシデントが発火すると、担当者に通知が届きます。

```bash
curl -X PUT http://localhost:8000/api/v1/schedules/default/oncall \
  -H "Content-Type: application/json" \
  -d '{"current_user_id": "<ステップ1で取得したユーザーID>"}'
```

`default` の部分はチーム名です。複数チームを運用する場合は任意の名前に変えてください。

<br><br>

---

<br><br>

### ステップ3: エスカレーションポリシーを設定する（任意）

一定時間応答がなかった場合に次の担当者へ通知をエスカレーションするポリシーを設定できます。

```bash
# ポリシーを作成
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{"name": "default policy", "team_name": "default"}'
```

レスポンスの `id`（policy_id）を使ってエスカレーション先を追加します。

```bash
# エスカレーション先を追加（step_order 順に通知される）
curl -X POST http://localhost:8000/api/v1/policies/<policy_id>/steps \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<ユーザーID>", "timeout_minutes": 10}'
```

ステップは複数追加できます。10分応答なし → 次のユーザーへ、という連鎖を作れます。

<br><br>

---

<br><br>

### ステップ4: アラートを送信する

監視システムや手動で `POST /api/v1/alerts` を叩くと、インシデントが発火して担当者に通知されます。

```bash
curl -X POST http://localhost:8000/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "サーバーCPU使用率 90%超",
    "description": "web-01 の CPU が閾値を超えています",
    "source": "prometheus",
    "team_name": "default",
    "priority": "P2"
  }'
```

`priority` は `P1`（最高）〜`P4`（最低）で指定します。`P1`/`P2` では通知にメンションが付きます。

> [!NOTE]
>
> `title` と `source` の組み合わせが同じアラートが既にオープン状態の場合、新しいインシデントは作成されず既存インシデントの `updated_at` が更新されます（重複排除）。

<br><br>

---

<br><br>

### ステップ5: インシデントを確認・対応する

ブラウザで http://localhost:8000 を開くとインシデント一覧が確認できます。
APIで操作する場合は以下のコマンドを使います。

```bash
# インシデント一覧を確認
curl http://localhost:8000/api/v1/incidents

# 対応開始（Acknowledge）
curl -X POST http://localhost:8000/api/v1/incidents/<incident_id>/acknowledge

# 解決（Resolve）
curl -X POST http://localhost:8000/api/v1/incidents/<incident_id>/resolve
```

Acknowledge するとエスカレーションが止まります。Resolve するとインシデントがクローズされます。

<br><br>

---

<br><br>

### メモを追加する

インシデントに対応メモを残せます。

```bash
curl -X POST http://localhost:8000/api/v1/incidents/<incident_id>/notes \
  -H "Content-Type: application/json" \
  -d '{"body": "web-01 を再起動して復旧しました", "author_user_id": "<ユーザーID>"}'
```

<br><br>

---

<br><br>

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

ユーザーにはSlack・Discordの個人Webhook URLを設定できます。インシデント発生時、担当ユーザーに個人URLが設定されていればそちらへ通知し、未設定の場合は `.env` のグローバルWebhookにフォールバックします。

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice",
    "email": "alice@example.com",
    "discord_webhook_url": "https://discord.com/api/webhooks/YOUR/PERSONAL_WEBHOOK",
    "slack_webhook_url": "https://hooks.slack.com/services/YOUR/PERSONAL_WEBHOOK"
  }'
```

### スケジュール

| メソッド | パス | 説明 |
|---|---|---|
| `PUT` | `/api/v1/schedules/{team_name}/oncall` | オンコール担当者の設定・切り替え |

対話型ドキュメント: http://localhost:8000/docs

<br><br>

---

<br><br>

## テスト用インシデントの発行

```bash
curl -X POST http://localhost:8000/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "テスト障害",
    "description": "テスト用のインシデントです",
    "source": "manual",
    "team_name": "default",
    "priority": "P3"
  }'
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `title` | ✓ | インシデントのタイトル |
| `description` | - | 詳細説明 |
| `source` | - | 発生源（例: `prometheus`, `manual`） |
| `team_name` | - | チーム名（デフォルト: `default`） |
| `priority` | - | `P1`〜`P5`（デフォルト: `P3`） |

> [!NOTE]
>
> `title` + `source` の組み合わせが同じ場合は重複排除され、新規作成ではなく既存インシデントの `updated_at` が更新されます。
