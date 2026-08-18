.PHONY: help up down update

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  up      起動"
	@echo "  down    停止"
	@echo "  update  pull → ビルド → 再起動 → マイグレーション"

up:
	docker compose up -d

down:
	docker compose down

update:
	git pull
	docker compose build --no-cache
	docker compose up -d
	docker compose exec web alembic upgrade head
