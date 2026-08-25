"""Safe, non-destructive Git synchronization for Colab research."""

import subprocess
from pathlib import Path
from typing import Tuple, Optional
from quant_platform.observability.logger import logger


class SafeGitSync:
    """Safely synchronizes code from GitHub without destroying local work."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or Path.cwd()

    def _run_git(self, args: list[str]) -> Tuple[int, str, str]:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()

    def get_git_info(self) -> dict:
        """Get current commit hash, branch, and dirty status."""
        rc, sha, _ = self._run_git(["rev-parse", "HEAD"])
        rc_b, branch, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        rc_s, status, _ = self._run_git(["status", "--porcelain"])

        return {
            "git_sha": sha if rc == 0 else "unknown",
            "branch": branch if rc_b == 0 else "unknown",
            "is_dirty": bool(status.strip()) if rc_s == 0 else False,
            "status_output": status,
        }

    def safe_pull(self) -> Tuple[bool, str]:
        """Perform fast-forward only pull. Abort if working tree is dirty."""
        info = self.get_git_info()
        if info["is_dirty"]:
            msg = f"Cannot pull: working tree is dirty. Modified files:\n{info['status_output']}"
            logger.warning(msg)
            return False, msg

        # Fetch latest
        rc_f, out_f, err_f = self._run_git(["fetch", "origin"])
        if rc_f != 0:
            return False, f"Git fetch failed: {err_f}"

        # Fast-forward pull
        rc_p, out_p, err_p = self._run_git(["pull", "--ff-only"])
        if rc_p != 0:
            return False, f"Git pull --ff-only failed: {err_p}"

        logger.info(f"Git pull successful: {out_p}")
        return True, out_p
