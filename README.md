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
<br><br>

---

<br><br>

## AI 調査エージェント

`AI_ENABLED=true`（デフォルト: 有効）の場合、インシデントに対して一次対応レポートを自動生成できます。

```bash
curl -X POST http://localhost:8000/api/v1/incidents/<incident_id>/investigate
```

**アラート受信時の動作フロー:**

```
POST /api/v1/alerts
        │
        ▼
  インシデント作成（即座に 201 レスポンス）
        │
        ▼（バックグラウンド）
  ┌─────────────────────────────────────────┐
  │  AI 初動対応（_ai_initial_response）     │
  │                                         │
  │  1. AI 調査レポート生成                  │
  │  2. インシデントにノートとして添付        │
  │  3. 《エスカレーション推奨》を判定        │
  │     │                                   │
  │   YES → 担当者に通知 + 通常タイマー      │
  │   NO  → 通知なし + 3倍の長いタイマー     │
  │   失敗 → フォールバック（即時通知）      │
  └─────────────────────────────────────────┘
```

> AI が無効（`AI_ENABLED=false`）の場合は従来通り即時通知・エスカレーションが動作します。

**エスカレーション推奨の判定:**

AI レポートの末尾に記載された構造化マーカーを解析します。

```
《エスカレーション推奨》: YES  → 担当者に即時通知し、通常のタイムアウトでエスカレーション
《エスカレーション推奨》: NO   → 通知を保留し、3 倍の長いタイムアウトで安全網として設定
```

YES と判断される典型例：サービス停止・P1/P2 障害・根本原因不明・広範囲な影響
NO と判断される典型例：既知の一過性エラー・影響範囲が限定的・自動復旧が期待できる
        │
        ▼
  QueryCache 確認 ── HIT → キャッシュ済みレポートを即返却
        │
       MISS
        │
        ▼
  topology-syslog インシデント？（タイトルに [INC-...] があるか）
        │
      YES → topology-syslog の AI レポートを取得
        │         ├─ 取得成功 → 行動指示特化プロンプト
        │         │         （チェックリスト・確認コマンド・顧客連絡文面）
        │         └─ 取得失敗 → 生ログ等詳細情報を取得
        │         （AI 無効等）     汎用プロンプトにフォールバック
        │
        NO → 汎用プロンプト（状況把握・推定原因・対応手順等）
        │
        ▼
  RAGStore で類似過去調査を検索
        │
        ▼
  LLM でレポート生成
        │
        ▼
  QueryCache + RAGStore に保存（次回の類似インシデントで再利用）
```

**topology-syslog インシデント時のレポート構成:**

| レポート | 生成元 | 読者 | 内容 |
|---|---|---|---|
| 技術分析 | topology-syslog AI | ネットワークエンジニア | 根本原因・影響ノード・生ログ解析・予防策 |
| **行動指示** | **vigil AI（本エンドポイント）** | **オンコール担当者** | **対応チェックリスト・確認コマンド・エスカレーション・顧客連絡文面** |

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `AI_ENABLED` | `true` | AI エージェントの有効化 |
| `LLM_PROVIDER` | `openai` | `openai` / `ollama` |
| `OPENAI_API_KEY` | — | OpenAI API キー |
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用モデル |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama の URL |
| `OLLAMA_MODEL` | `llama3` | Ollama のモデル名 |
| `AI_RAG_PATH` | `./data/.chromadb` | RAG ベクターストアの保存先 |
| `AI_CACHE_TTL_DAYS` | `7` | キャッシュ有効期間（日） |
| `TOPOLOGY_SYSLOG_URL` | — | topology-syslog の URL（設定時は詳細情報を取得） |

<br><br>

---

<br><br>

## 長期稼働に関する注意事項

### Docker ログローテーション

`docker-compose.yml` に `json-file` ドライバの `max-size` / `max-file` を設定しています。

| コンテナ | 最大サイズ | 保持ファイル数 | 最大合計 |
|---|---|---|---|
| web | 10 MB | 5 | 50 MB |

### AI クエリキャッシュの自動クリーンアップ

AI 調査レポートのキャッシュ（`vigil_ai_cache` テーブル）は、TTL (`AI_CACHE_TTL_DAYS`、デフォルト 7 日) 切れの行を **24 時間ごと**に自動削除します。キャッシュはインシデント DB と同じ SQLite ファイル内に保存されます。

### RAG ストア（ChromaDB）

調査履歴を蓄積する ChromaDB は `AI_RAG_PATH`（デフォルト: `./data/.chromadb`）に保存されます。
Docker 環境では `./data` ボリューム内に収まるため、コンテナを再起動してもデータは消失しません。

```bash
# ChromaDB をリセットする場合
docker compose down
rm -rf data/.chromadb
docker compose up -d
```