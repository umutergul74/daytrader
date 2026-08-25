# ADR 0001: Colab-First Interactive Research and Google Drive Persistent Storage

## Context
Google Colab provides high-performance on-demand computing (CPUs, high-RAM, and GPUs) at minimal cost for quantitative research. However, Colab runtimes are strictly ephemeral—instances can disconnect or be recycled at any moment. Furthermore, direct random I/O on Google Drive mounted filesystem (`/content/drive`) is slow when dealing with millions of small read/write operations.

## Decision
1. **GitHub** is the authoritative source of truth for all source code, tests, and documentation.
2. **Google Drive** (`/content/drive/MyDrive/ETHQuantPlatform/`) acts as cold persistent backing storage for canonical datasets, model checkpoints, experiment indices, and reports.
3. **Local `/content` Scratch Space** is the active high-speed workspace. Data partitions are copied from Drive to `/content` on startup, processed locally with Polars/DuckDB, and compact checkpoints/manifests are atomically synced back to Drive upon experiment completion.
4. **Hardware Detection**: The runtime gracefully detects CPU vs CUDA GPU capabilities and runs CPU-vectorized workloads without failing if GPU is unavailable.

## Status
Accepted.
