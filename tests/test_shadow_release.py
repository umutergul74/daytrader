"""Tests for Shadow Baseline Release Manager."""

import tempfile
from pathlib import Path
from quant_platform.live.shadow_release import ShadowReleaseManager


def test_shadow_baseline_creation_and_loading():
    """Verify creating and loading frozen shadow-baseline-v1 release manifest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest = ShadowReleaseManager.create_shadow_baseline_v1(releases_dir=tmp_path)

        assert manifest.release_id == "shadow-baseline-v1"
        assert manifest.is_frozen is True
        assert manifest.champion_strategy.component_name == "LiquiditySweepFVGStrategy"
        assert manifest.champion_strategy.version == "v2"
        assert len(manifest.challengers) == 2

        # Verify load
        loaded = ShadowReleaseManager.load_release(release_id="shadow-baseline-v1", releases_dir=tmp_path)
        assert loaded.release_id == manifest.release_id
        assert loaded.git_sha == manifest.git_sha
        assert loaded.risk_configuration["risk_per_trade_fraction"] == 0.01
