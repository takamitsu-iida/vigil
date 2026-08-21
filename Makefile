.PHONY: help up down logs update clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  up      起動"
	@echo "  down    停止"
	@echo "  logs    ログ表示"
	@echo "  update  pull → ビルド → 再起動 → マイグレーション"
	@echo "  clean   コンテナ・イメージ・ボリュームを削除"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

update:
	git pull
	docker compose build --no-cache
	docker compose up -d

clean:
	docker compose down --rmi all --volumes --remove-orphans
