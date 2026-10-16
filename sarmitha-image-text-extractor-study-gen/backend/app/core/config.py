from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    srcnn_modal_url: str = ""
    trocr_modal_url: str = ""
    trocr_lines_modal_url: str = ""
    qwen_modal_url: str = ""
    sinhalm_modal_url: str = ""
    visual_ocr_modal_url: str = ""
    translate_modal_url: str = ""

    allowed_origins: str = "http://localhost:3000"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_publishable_key: SecretStr = SecretStr("")
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_feedback_bucket: str = "ocr-feedback"
    supabase_history_bucket: str = "ocr-history"
    auth_site_url: str = "https://sarmitha-ocr.vercel.app"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
