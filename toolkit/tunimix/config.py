"""Settings, read from environment variables or a .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(Path.cwd() / ".env")
_load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    # rules = no AI (default, offline, free) | ai = use the provider below
    engine: str = field(default_factory=lambda: os.getenv("TUNIMIX_ENGINE", "rules").lower())
    # anthropic | openai | gemini | openrouter | groq | mistral | deepseek | ollama | lmstudio | custom
    provider: str = field(default_factory=lambda: os.getenv("TUNIMIX_PROVIDER", "anthropic").lower())
    base_url: str = field(default_factory=lambda: os.getenv("TUNIMIX_BASE_URL", ""))
    api_key: str = field(default_factory=lambda: os.getenv("TUNIMIX_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "") or (
        os.getenv("TUNIMIX_API_KEY", "") if os.getenv("TUNIMIX_PROVIDER", "anthropic").lower() == "anthropic" else ""))
    model: str = field(default_factory=lambda: os.getenv("TUNIMIX_MODEL", "") or (
        "claude-sonnet-5-5" if os.getenv("TUNIMIX_PROVIDER", "anthropic").lower() == "anthropic" else ""))
    recipe_language: str = field(default_factory=lambda: os.getenv("TUNIMIX_LANGUAGE", "de"))
    machine: str = field(default_factory=lambda: os.getenv("TUNIMIX_MACHINE", "TM6"))
    library_dir: Path = field(default_factory=lambda: Path(os.getenv("TUNIMIX_LIBRARY", ROOT / "library")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("TUNIMIX_OUTPUT", ROOT / "output")))

    cookidoo_email: str = field(default_factory=lambda: os.getenv("COOKIDOO_EMAIL", ""))
    cookidoo_password: str = field(default_factory=lambda: os.getenv("COOKIDOO_PASSWORD", ""))
    cookidoo_country: str = field(default_factory=lambda: os.getenv("COOKIDOO_COUNTRY", "de"))
    cookidoo_language: str = field(default_factory=lambda: os.getenv("COOKIDOO_LANGUAGE", "de-DE"))
    upload_delay_s: float = field(default_factory=lambda: float(os.getenv("COOKIDOO_UPLOAD_DELAY", "12")))

    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_allowed_users: list[int] = field(default_factory=lambda: [
        int(x) for x in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()])

    def require_anthropic(self) -> None:
        if not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example).")

    def require_llm(self) -> None:
        if self.provider == "anthropic":
            return self.require_anthropic()
        from .convert.providers import resolve
        resolve(self.provider, self.base_url, self.api_key)
        if not self.model:
            raise RuntimeError(f"TUNIMIX_MODEL is not set for provider '{self.provider}' "
                               f"(list models with: tunimix models).")

    def require_cookidoo(self) -> None:
        if not (self.cookidoo_email and self.cookidoo_password):
            raise RuntimeError("COOKIDOO_EMAIL / COOKIDOO_PASSWORD are not set (see .env.example).")


settings = Settings()
