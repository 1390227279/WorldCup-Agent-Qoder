"""Application configuration.

All settings are loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Central configuration for the WorldCup Predictor Agent."""

    # ── Qwen Agent ──────────────────────────────────────────
    qwen_api_key: str = field(
        default_factory=lambda: os.getenv("QWEN_API_KEY", "")
    )
    qwen_model: str = field(
        default_factory=lambda: os.getenv("QWEN_MODEL", "qwen-max")
    )
    agent_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("AGENT_TIMEOUT", "15"))
    )
    agent_max_retries: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_RETRIES", "2"))
    )

    # ── Circuit Breaker ─────────────────────────────────────
    circuit_breaker_failure_threshold: int = field(
        default_factory=lambda: int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
    )
    circuit_breaker_recovery_seconds: int = field(
        default_factory=lambda: int(os.getenv("CIRCUIT_BREAKER_RECOVERY", "30"))
    )

    # ── Database ────────────────────────────────────────────
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./worldcup.db",
        )
    )

    # ── CORS ────────────────────────────────────────────────
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    # ── Server ──────────────────────────────────────────────
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))


settings = Settings()
