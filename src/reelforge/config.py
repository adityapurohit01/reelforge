"""Configuration loader for ReelForge, combining pydantic-settings with config.yaml."""
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProductConfig(BaseModel):
    name: str = "Vocalis AI"
    tagline: str = "Never miss a customer call again."
    cta_url: str = "vocalis.ai"
    cta_handle: str = "@vocalis.ai"
    brand_colors: Dict[str, str] = Field(
        default_factory=lambda: {
            "primary": "#6366F1",
            "secondary": "#EC4899",
            "background": "#0F172A",
            "text": "#F8FAFC",
            "accent": "#10B981",
        }
    )


class PipelineConfig(BaseModel):
    dry_run: bool = True
    auto_publish: bool = False
    videos_per_day: int = 2
    publish_time_windows: List[str] = Field(default_factory=lambda: ["10:30", "18:00"])
    timezone: str = "UTC"
    exploration_floor: float = 0.30


class CooldownsConfig(BaseModel):
    vertical: int = 5
    city: int = 6
    scenario: int = 4
    hook_style: int = 8
    layout_palette: int = 6
    palette_alone: int = 3
    voice_pair: int = 4
    agent_voice_max_in_5: int = 2
    first_line_or_cta: int = 15


class SimilarityThresholdsConfig(BaseModel):
    script_cosine_max: float = 0.82
    hook_cosine_max: float = 0.85
    trigram_jaccard_max: float = 0.25
    history_window: int = 50


class DurationBoundsConfig(BaseModel):
    min_seconds: float = 20.0
    max_seconds: float = 40.0
    target_min_spoken: float = 22.0
    target_max_spoken: float = 38.0


class QCThresholdsConfig(BaseModel):
    target_lufs: float = -14.0
    lufs_tolerance: float = 1.5
    max_true_peak_dbtp: float = -1.5
    max_silence_duration_s: float = 1.2
    max_wer: float = 0.15
    max_freeze_duration_s: float = 1.5


class ModelsConfig(BaseModel):
    llm_model: str = "llama3.1:latest"
    llm_fallback: str = "llama3.2:3b"
    embedding_model: str = "nomic-embed-text"
    tts_engine: str = "kokoro"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"


class StorageConfig(BaseModel):
    backend: str = "local"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_chat_ids: Optional[str] = Field(default=None, alias="TELEGRAM_ALLOWED_CHAT_IDS")

    # Meta / Instagram
    ig_user_id: Optional[str] = Field(default=None, alias="IG_USER_ID")
    ig_access_token: Optional[str] = Field(default=None, alias="IG_ACCESS_TOKEN")
    meta_app_id: Optional[str] = Field(default=None, alias="META_APP_ID")
    meta_app_secret: Optional[str] = Field(default=None, alias="META_APP_SECRET")
    graph_api_version: str = Field(default="v20.0", alias="GRAPH_API_VERSION")

    # Cloudflare R2
    r2_account_id: Optional[str] = Field(default=None, alias="R2_ACCOUNT_ID")
    r2_access_key_id: Optional[str] = Field(default=None, alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: Optional[str] = Field(default=None, alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(default="reelforge-videos", alias="R2_BUCKET")
    r2_public_base_url: str = Field(default="https://pub-reelforge.r2.dev", alias="R2_PUBLIC_BASE_URL")

    # Ollama
    ollama_host: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_HOST")

    @property
    def allowed_telegram_chats(self) -> List[int]:
        if not self.telegram_allowed_chat_ids:
            return []
        return [int(cid.strip()) for cid in self.telegram_allowed_chat_ids.split(",") if cid.strip()]


class ReelForgeConfig(BaseModel):
    product: ProductConfig = Field(default_factory=ProductConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    cooldowns: CooldownsConfig = Field(default_factory=CooldownsConfig)
    similarity_thresholds: SimilarityThresholdsConfig = Field(default_factory=SimilarityThresholdsConfig)
    duration_bounds: DurationBoundsConfig = Field(default_factory=DurationBoundsConfig)
    qc_thresholds: QCThresholdsConfig = Field(default_factory=QCThresholdsConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    settings: AppSettings = Field(default_factory=AppSettings)


def load_config(config_path: Path = Path("config.yaml")) -> ReelForgeConfig:
    data: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = loaded

    settings = AppSettings()
    return ReelForgeConfig(
        product=ProductConfig(**data.get("product", {})),
        pipeline=PipelineConfig(**data.get("pipeline", {})),
        cooldowns=CooldownsConfig(**data.get("cooldowns", {})),
        similarity_thresholds=SimilarityThresholdsConfig(**data.get("similarity_thresholds", {})),
        duration_bounds=DurationBoundsConfig(**data.get("duration_bounds", {})),
        qc_thresholds=QCThresholdsConfig(**data.get("qc_thresholds", {})),
        models=ModelsConfig(**data.get("models", {})),
        storage=StorageConfig(**data.get("storage", {})),
        settings=settings,
    )
