# インシデント管理ツール 仕様書

## 1. 概要
Python (FastAPI) をベースとした、セルフホスト可能な軽量オープンソースのインシデント管理・オンコールツールです。

## 2. 技術スタック
- **言語/フレームワーク:** Python 3.11+, FastAPI (高速かつ非同期処理が得意)
- **データベース:** SQLite (Alembicでのマイグレーション、SQLAlchemy or SQLModelによるORM)
- **バックグラウンド処理:** FastAPI BackgroundTasks (または軽量な APScheduler)
- **通知:** Slack / Discord Webhooks
- **UI:** Jinja2 + HTMX + Tailwind CSS (SPAの複雑さを排除)

## 3. データモデル (SQLModel / SQLAlchemy)

### 3.1 Users (ユーザー)
- `id`: str (UUID) - プライマリキー
- `name`: str - ユーザー名
- `slack_user_id`: str - Slackのメンション用ID
- `email`: str - メールアドレス

### 3.2 Schedules (オンコールスケジュール)
- `id`: str (UUID)
- `team_name`: str
- `current_user_id`: str (Users.idへの外部キー)
- `rotation_interval`: str (例: "weekly")

### 3.3 Incidents (インシデント)
- `id`: str (UUID)
- `title`: str - アラートのタイトル
- `description`: str - 詳細情報
- `status`: str (`triggered` / `acknowledged` / `resolved`)
- `assigned_user_id`: str (Users.idへの外部キー)
- `created_at`: datetime
- `updated_at`: datetime

## 4. API設計 (FastAPI)

### 4.1 アラート受信
- **Endpoint:** `POST /api/v1/alerts`
- **Request Body:**
  ```json
  {
    "title": "CPU Usage High",
    "description": "Server A CPU usage is over 90%",
    "source": "Prometheus"
  }
  ```
- **動作:**
  1. インシデントを `triggered` でDBに保存。
  2. 現在のオンコール担当者を特定。
  3. Slackへ通知を送信。
  4. バックグラウンドでエスカレーションタイマーを起動。

### 4.2 インシデント操作
- **Endpoint:** `POST /api/v1/incidents/{id}/acknowledge`
  - 担当者が確認したことを記録（ステータスを `acknowledged` に変更し、エスカレーションタイマーを停止）。
- **Endpoint:** `POST /api/v1/incidents/{id}/resolve`
  - 障害が復旧したことを記録（ステータスを `resolved` に変更）。

## 5. エスカレーション・バックグラウンド処理
- FastAPIの `BackgroundTasks` または `APScheduler` を利用。
- インシデント発生から **10分間** ステータスが `triggered` のままであった場合、次のオンコール担当者（またはチームチャンネル）へ再通知を行う。

## 6. ディレクトリ構成案
```text
vigil/
├── main.py            # FastAPIエントリーポイント
├── database.py        # DB接続設定
├── models.py          # SQLModel定義
├── crud.py            # DB操作ロジック
├── routers/
│   ├── api.py         # Webhook / APIエンドポイント
│   └── web.py         # HTMX用UI画面
├── services/
│   ├── notifier.py    # Slack/Discord通知ロジック
│   └── escalation.py  # エスカレーション管理
├── requirements.txt
└── Dockerfile
```

## 7. デプロイメント
- `Dockerfile` と `docker-compose.yml` を用意し、`docker compose up -d` のみでデータ永続化（SQLiteのボリュームマウント）を含めて即座に起動できるようにする。