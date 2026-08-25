"""Typed application settings using Pydantic Settings."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class PlatformSettings(BaseSettings):
    """Platform configuration settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base Paths
    PROJECT_ROOT: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent
    )
    DRIVE_PERSISTENT_ROOT: Path = Path("/content/drive/MyDrive/ETHQuantPlatform")
    LOCAL_DATA_DIR: Path = Field(default=Path("data"))
    LOCAL_RESEARCH_DIR: Path = Field(default=Path("research"))
    LOCAL_REPORTS_DIR: Path = Field(default=Path("reports"))
    LOCAL_MLRUNS_DIR: Path = Field(default=Path("mlruns"))

    # Mode and Safety
    LIVE_TRADING_ENABLED: bool = False
    EXECUTION_POLICY: str = "NO_REAL_MONEY"
    ENVIRONMENT: str = "development"  # colab, local, vps

    # Market Defaults
    DEFAULT_SYMBOL: str = "ETHUSDT"
    CANONICAL_TIMEFRAME: str = "1m"

    # API Keys / Secrets (Optional for public research/shadow mode)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    @property
    def raw_data_dir(self) -> Path:
        return self.LOCAL_DATA_DIR / "raw"

    @property
    def canonical_data_dir(self) -> Path:
        return self.LOCAL_DATA_DIR / "canonical"

    @property
    def manifest_data_dir(self) -> Path:
        return self.LOCAL_DATA_DIR / "manifests"

    @property
    def research_ledger_dir(self) -> Path:
        return self.LOCAL_RESEARCH_DIR / "ledger"

    def ensure_directories(self) -> None:
        """Ensure all required local working directories exist."""
        for d in [
            self.raw_data_dir,
            self.canonical_data_dir,
            self.manifest_data_dir,
            self.research_ledger_dir,
            self.LOCAL_REPORTS_DIR,
            self.LOCAL_MLRUNS_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = PlatformSettings()
