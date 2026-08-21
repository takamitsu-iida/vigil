from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/incident.db"
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    escalation_timeout_minutes: int = 10
    base_url: str = "http://localhost:8000"  # 通知リンク生成に使用

    # AI 調査エージェント
    ai_enabled: bool = True
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ai_rag_path: str = "./data/.chromadb"  # Docker ボリューム内に収める
    ai_cache_ttl_days: int = 7
    topology_syslog_url: str = ""  # 設定すると topology-syslog から詳細を取得


settings = Settings()
