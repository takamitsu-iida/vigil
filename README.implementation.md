# インシデント管理ツール 実装計画

## 進捗サマリー

| フェーズ | タスク数 | 完了 | 状態 |
|----------|----------|------|------|
| Phase 1: プロジェクト基盤 | 6 | 6 | 完了 ✅ |
| Phase 2: データモデル & DB | 5 | 5 | 完了 ✅ |
| Phase 3: コアAPI | 7 | 7 | 完了 ✅ |
| Phase 4: 通知 & エスカレーション | 5 | 5 | 完了 ✅ |
| Phase 5: Web UI | 6 | 6 | 完了 ✅ |
| Phase 6: デプロイ & 仕上げ | 5 | 5 | 完了 ✅ |
| Phase 7: 機能アップデート | 16 | 16 | 完了 ✅ |

---

## Phase 1: プロジェクト基盤

**目標:** リポジトリ構造・依存関係・設定管理の土台を整える

- [x] **1-1** ディレクトリ構造の作成
  `vigil/` 配下に `routers/`, `services/`, `templates/`, `static/` を作成する

- [x] **1-2** `requirements.txt` の作成
  ```
  fastapi>=0.111.0
  uvicorn[standard]>=0.29.0
  sqlmodel>=0.0.19
  alembic>=1.13.0
  httpx>=0.27.0        # Slack/Discord Webhook送信
  apscheduler>=3.10.0  # エスカレーションタイマー
  jinja2>=3.1.0
  python-multipart>=0.0.9
  ```

- [x] **1-3** `pyproject.toml` の作成
  Python 3.11+ を明示し、ツール設定 (ruff, mypy) を記述する

- [x] **1-4** `config.py` の作成
  `pydantic-settings` で環境変数を管理する
  ```
  DATABASE_URL, SLACK_WEBHOOK_URL, DISCORD_WEBHOOK_URL,
  ESCALATION_TIMEOUT_MINUTES (デフォルト10)
  ```

- [x] **1-5** `.env.example` の作成
  開発者がすぐ試せるよう必須環境変数のサンプルを記述する

- [x] **1-6** `main.py` のスケルトン作成
  FastAPIアプリ初期化・ルーター登録・lifespan イベントの骨格のみ実装する

---

## Phase 2: データモデル & DB

**目標:** SQLModel 定義・Alembicマイグレーション・CRUD層の実装

- [x] **2-1** `database.py` の作成
  SQLite エンジン生成・セッションファクトリ・`create_db_and_tables()` を実装する

- [x] **2-2** `models.py` の作成
  仕様書 §3 に従い以下の SQLModel クラスを定義する
  - `User` (`id`=UUID, `name`, `slack_user_id`, `email`)
  - `Schedule` (`id`=UUID, `team_name`, `current_user_id` FK, `rotation_interval`)
  - `Incident` (`id`=UUID, `title`, `description`, `status`, `assigned_user_id` FK, `created_at`, `updated_at`)
  - Enum `IncidentStatus` (`triggered` / `acknowledged` / `resolved`)

- [x] **2-3** Alembic の初期化と最初のマイグレーション生成
  `alembic init alembic` 後、`env.py` に SQLModel のメタデータを接続する

- [x] **2-4** `crud.py` の作成
  各モデルの基本操作を実装する
  - `get_user`, `create_user`, `list_users`
  - `get_schedule_by_team`, `update_oncall_user`
  - `create_incident`, `get_incident`, `update_incident_status`, `list_incidents`

- [x] **2-5** `crud.py` の単体テスト作成
  `pytest` + インメモリ SQLite でCRUD操作を検証する
  (`tests/test_crud.py`)

---

## Phase 3: コアAPI

**目標:** アラート受信・インシデント操作の REST API を実装する

- [x] **3-1** `routers/api.py` のスケルトン作成
  `APIRouter(prefix="/api/v1")` を作成し `main.py` に登録する

- [x] **3-2** `POST /api/v1/alerts` の実装
  仕様書 §4.1 の4ステップを順番に実装する
  1. インシデントを `triggered` でDB保存
  2. 現在オンコール担当者を取得
  3. `notifier.send_alert()` を `BackgroundTasks` で非同期実行
  4. エスカレーションタイマーを起動

- [x] **3-3** `POST /api/v1/incidents/{id}/acknowledge` の実装
  ステータスを `acknowledged` に更新しエスカレーションをキャンセルする

- [x] **3-4** `POST /api/v1/incidents/{id}/resolve` の実装
  ステータスを `resolved` に更新する

- [x] **3-5** `GET /api/v1/incidents` の実装
  フィルタリング (`status`, `limit`, `offset`) 付きでインシデント一覧を返す

- [x] **3-6** ユーザー・スケジュール管理API の実装
  - `POST /api/v1/users`
  - `GET  /api/v1/users`
  - `PUT  /api/v1/schedules/{team_name}/oncall` (オンコール担当者の切り替え)

- [x] **3-7** APIエンドポイントの統合テスト作成
  `pytest` + `httpx.AsyncClient` + `TestClient` でエンドポイントを検証する
  (`tests/test_api.py`)

---

## Phase 4: 通知 & エスカレーション

**目標:** Slack/Discord 通知とエスカレーション自動再通知を実装する

- [x] **4-1** `services/notifier.py` の実装
  - `send_alert(incident, user)`: Slack/Discord Webhook へ `httpx` で POST
  - メッセージフォーマット: タイトル・説明・担当者・ステータスを含む
  - 設定が空の場合はスキップ（ログのみ）

- [x] **4-2** `services/escalation.py` の実装
  - `APScheduler` の `AsyncIOScheduler` を使用
  - `schedule_escalation(incident_id, timeout_minutes)`: タイマー登録
  - `cancel_escalation(incident_id)`: タイマーキャンセル
  - タイムアウト時: DB を再確認し `triggered` のままなら再通知

- [x] **4-3** `main.py` の lifespan にスケジューラの起動/停止を組み込む

- [x] **4-4** 通知サービスの単体テスト作成
  `httpx` の `MockTransport` で Webhook 送信をモックしてテストする
  (`tests/test_notifier.py`)

- [x] **4-5** エスカレーション動作の統合テスト作成
  タイムアウト値を短く設定し、エスカレーション発火を検証する
  (`tests/test_escalation.py`)

---

## Phase 5: Web UI

**目標:** Jinja2 + HTMX + Tailwind CSS によるサーバーサイドUI の実装

- [x] **5-1** ベーステンプレートの作成
  `templates/base.html`: Tailwind CSS CDN・HTMX CDN を読み込む共通レイアウト

- [x] **5-2** `routers/web.py` のスケルトン作成
  `APIRouter` を作成し、Jinja2Templates を設定して `main.py` に登録する

- [x] **5-3** インシデント一覧ページの実装
  - `GET /` → `templates/index.html`
  - ステータスバッジ（色分け）・HTMX でポーリング更新 (`hx-trigger="every 30s"`)

- [x] **5-4** インシデント詳細ページの実装
  - `GET /incidents/{id}` → `templates/incident_detail.html`
  - Acknowledge / Resolve ボタン (HTMX `hx-post` でAPI呼び出し)

- [x] **5-5** オンコール管理ページの実装
  - `GET /schedules` → `templates/schedules.html`
  - 現在の担当者表示・担当者切り替えフォーム

- [x] **5-6** ユーザー管理ページの実装
  - `GET /users` → `templates/users.html`
  - ユーザー追加フォーム（HTMX `hx-post`）

---

## Phase 6: デプロイ & 仕上げ

**目標:** Docker化・ドキュメント整備・最終動作確認

- [x] **6-1** `Dockerfile` の作成
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["uvicorn", "vigil.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [x] **6-2** `docker-compose.yml` の作成
  SQLite ファイルを `./data` ボリュームにマウントし
  `docker compose up -d` 一発で起動できるよう設定する

- [x] **6-3** `README.md` の作成
  - クイックスタート手順 (docker compose / ローカル起動)
  - 環境変数一覧
  - APIエンドポイント一覧
  - スクリーンショット枠

- [x] **6-4** CI設定の作成 (`.github/workflows/ci.yml`)
  `pytest` + `ruff` lint を GitHub Actions で自動実行する

- [x] **6-5** エンドツーエンド動作確認
  - `docker compose up` でサービス起動
  - `POST /api/v1/alerts` でインシデント発火
  - 10分エスカレーション確認
  - Acknowledge / Resolve の動作確認
  - UIからの一連操作確認

---

## 実装順序と依存関係

```
Phase 1 (基盤)
    └── Phase 2 (DB/モデル)
            ├── Phase 3 (API) ──── Phase 5 (UI)
            └── Phase 4 (通知)         │
                    │                  │
                    └────── Phase 6 (デプロイ/仕上げ) ──┘
                                       │
                                  Phase 7 (機能アップデート)
```

---

## Phase 7: 機能アップデート

**目標:** 実運用に耐えうる品質に引き上げる

### 7-A: インシデント優先度 (Priority)

- [x] **7-A-1** `Priority` Enum の追加 (`models.py`)
  `P1 (critical)` / `P2 (high)` / `P3 (medium)` / `P4 (low)` の4段階

- [x] **7-A-2** `Incident` モデルに `priority` フィールドを追加
  デフォルト `P3`。Alembic マイグレーションも生成する

- [x] **7-A-3** `POST /api/v1/alerts` で `priority` を受け取れるよう `AlertIn` を拡張

- [x] **7-A-4** 通知メッセージに優先度を含める (`notifier.py`)
  P1/P2 の場合は `@channel` メンションなど強調表現を追加する

- [x] **7-A-5** Web UI のインシデント一覧・詳細に優先度バッジを表示
  P1=赤・P2=橙・P3=黄・P4=灰 で色分けする

### 7-B: アラート重複排除 (Deduplication)

- [x] **7-B-1** `Incident` モデルに `fingerprint` フィールドを追加
  `source + title` のハッシュ値。Alembic マイグレーションも生成する

- [x] **7-B-2** `POST /api/v1/alerts` でフィンガープリントによる重複チェックを実装
  同一フィンガープリントの `triggered` / `acknowledged` インシデントが存在する場合は
  新規作成せず既存インシデントの `updated_at` を更新して返す

- [x] **7-B-3** 重複排除ロジックの単体テスト作成 (`tests/test_dedup.py`)

### 7-C: 多段階エスカレーション

- [x] **7-C-1** `EscalationPolicy` / `EscalationStep` モデルの追加 (`models.py`)
  - `EscalationPolicy`: `id`, `name`, `team_name`
  - `EscalationStep`: `id`, `policy_id` FK, `step_order`, `user_id` FK, `timeout_minutes`
  - Alembic マイグレーションも生成する

- [x] **7-C-2** エスカレーションポリシーの CRUD 実装 (`crud.py`)
  `create_policy`, `add_step`, `get_steps_for_policy`, `get_policy_by_team`

- [x] **7-C-3** `escalation.py` を多段階対応に更新
  タイムアウト時に現在のステップの次のステップへ進み、各ステップのユーザーに通知する
  最終ステップ以降はそのまま再通知を継続する

- [x] **7-C-4** `POST /api/v1/alerts` のエスカレーション起動を新ポリシーに対応
  ポリシー未設定のチームは Phase 4 の単一タイムアウト動作にフォールバックする

- [x] **7-C-5** エスカレーションポリシー管理 API の実装
  - `POST /api/v1/policies`
  - `GET  /api/v1/policies/{team_name}`
  - `POST /api/v1/policies/{id}/steps`

### 7-D: インシデントコメント / タイムライン

- [x] **7-D-1** `IncidentNote` モデルの追加 (`models.py`)
  `id`, `incident_id` FK, `author_user_id` FK (nullable), `body`, `created_at`
  Alembic マイグレーションも生成する

- [x] **7-D-2** コメント CRUD の実装 (`crud.py`)
  `add_note`, `list_notes`

- [x] **7-D-3** コメント API の実装
  - `POST /api/v1/incidents/{id}/notes`
  - `GET  /api/v1/incidents/{id}/notes`

- [x] **7-D-4** インシデント詳細ページにタイムラインを追加 (`templates/incident_detail.html`)
  コメント一覧表示 + HTMX `hx-post` による投稿フォーム

## 技術的決定事項・注意点

| 項目 | 決定内容 | 理由 |
|------|----------|------|
| スケジューラ | APScheduler `AsyncIOScheduler` | FastAPI の非同期ループと統合しやすい |
| ORM | SQLModel | FastAPI / Pydantic との型整合性が高い |
| HTTP クライアント | httpx (非同期) | FastAPI の `BackgroundTasks` と相性が良い |
| Alembic マイグレーション | `autogenerate` を使用 | モデル変更を自動検出できる |
| テスト DB | インメモリ SQLite (`sqlite:///:memory:`) | テストの高速化・独立性の確保 |
| Tailwind CSS | CDN版 (Play CDN) | ビルドステップ不要でシンプルに保つ |
