"""Google Drive Persistence Manager for high-speed scratch vs persistent storage."""

import os
from pathlib import Path
import shutil
from typing import Optional
from quant_platform.config.settings import settings
from quant_platform.observability.logger import logger


class DrivePersistenceManager:
    """Synchronizes datasets and research artifacts between local workspace and Google Drive."""

    def __init__(self, drive_root: Optional[Path] = None, local_root: Optional[Path] = None):
        self.drive_root = drive_root or settings.DRIVE_PERSISTENT_ROOT
        self.local_root = local_root or settings.PROJECT_ROOT

    def is_drive_mounted(self) -> bool:
        """Check if Google Drive is mounted at /content/drive."""
        return Path("/content/drive/MyDrive").exists() or self.drive_root.exists()

    def mount_drive_in_colab(self) -> bool:
        """Mount Google Drive if running in Google Colab."""
        try:
            from google.colab import drive # type: ignore
            drive.mount('/content/drive')
            return True
        except Exception as e:
            logger.warning(f"Could not mount Google Drive via google.colab: {e}")
            return False

    def init_drive_layout(self) -> None:
        """Initialize folder layout on Google Drive."""
        if not self.is_drive_mounted():
            logger.warning(f"Drive root {self.drive_root} not accessible. Skipping Drive init.")
            return

        for sub in [
            "data/raw", "data/canonical", "data/manifests",
            "research/ledger", "research/checkpoints",
            "ml/models", "reports", "runtime"
        ]:
            (self.drive_root / sub).mkdir(parents=True, exist_ok=True)
        logger.info(f"Drive persistent folder layout initialized at {self.drive_root}")

    def sync_to_drive(self, relative_path: str) -> None:
        """Safely copy a local directory or file to Google Drive."""
        if not self.is_drive_mounted():
            return

        src = self.local_root / relative_path
        dst = self.drive_root / relative_path

        if not src.exists():
            return

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            for item in src.glob("**/*"):
                if item.is_file():
                    rel_item = item.relative_to(src)
                    target_file = dst / rel_item
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_file)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        logger.info(f"Synced {src} -> {dst}")

    def restore_from_drive(self, relative_path: str) -> None:
        """Restore dataset or research artifacts from Drive to local fast scratch."""
        if not self.is_drive_mounted():
            return

        src = self.drive_root / relative_path
        dst = self.local_root / relative_path

        if not src.exists():
            return

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            for item in src.glob("**/*"):
                if item.is_file():
                    rel_item = item.relative_to(src)
                    target_file = dst / rel_item
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    if not target_file.exists() or target_file.stat().st_mtime < item.stat().st_mtime:
                        shutil.copy2(item, target_file)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        logger.info(f"Restored {src} -> {dst}")
