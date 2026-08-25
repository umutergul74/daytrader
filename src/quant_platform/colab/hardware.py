"""Hardware and Colab environment detector."""

import os
import platform
import shutil
import sys
from typing import Optional, Dict, Any
from pydantic import BaseModel


class SystemResources(BaseModel):
    is_colab: bool
    os_name: str
    python_version: str
    cpu_count: int
    ram_gb: float
    disk_free_gb: float
    gpu_available: bool
    gpu_name: Optional[str] = None
    cuda_version: Optional[str] = None


class ResourceDetector:
    """Detects CPU, RAM, Disk, and GPU hardware capabilities."""

    @staticmethod
    def detect() -> SystemResources:
        is_colab = "google.colab" in sys.modules or os.path.exists("/content")
        os_name = platform.system()
        py_ver = platform.python_version()
        cpu_count = os.cpu_count() or 1

        # RAM detection
        ram_gb = 0.0
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            ram_gb = 8.0  # Fallback estimate

        # Disk detection
        total, used, free = shutil.disk_usage(os.getcwd())
        disk_free_gb = round(free / (1024 ** 3), 2)

        # GPU detection
        gpu_available = False
        gpu_name = None
        cuda_ver = None

        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_name = torch.cuda.get_device_name(0)
                cuda_ver = torch.version.cuda
        except Exception:
            pass

        return SystemResources(
            is_colab=is_colab,
            os_name=os_name,
            python_version=py_ver,
            cpu_count=cpu_count,
            ram_gb=ram_gb,
            disk_free_gb=disk_free_gb,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            cuda_version=cuda_ver,
        )
