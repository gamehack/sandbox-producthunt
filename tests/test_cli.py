from argparse import Namespace

import pytest

from sandbox_producthunt import cli
from qjai_producthunt.settings import Settings


@pytest.mark.asyncio
async def test_ready_preflight_skips_model(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCTHUNT_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("PRODUCTHUNT_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("PRODUCTHUNT_SOURCE", "producthunt")
    monkeypatch.setenv("PRODUCT_HUNT_COMMERCIAL_AUTHORIZED", "true")
    monkeypatch.setattr(cli, "_require_notion_config", lambda: None)
    monkeypatch.setattr(cli, "ready", lambda day: True)
    def forbidden(*args):
        raise AssertionError("must not call model")
    monkeypatch.setattr(cli, "make_runtime", forbidden)
    result = await cli.execute(Namespace(root=str(tmp_path), env=None, runtime="dsh",
                                         command="run", date="2026-11-25"))
    assert result["status"] == "already_ready"


def test_openai_runtime_reports_missing_omniroute_settings(tmp_path):
    settings = Settings(
        source="producthunt", fixture_path=tmp_path / "fixture.json",
        database_path=tmp_path / "db.sqlite", output_dir=tmp_path / "output",
        opportunity_threshold=60, max_research=5, ph_token="",
        ph_commercial_authorized=False, omni_base_url="", omni_api_key="",
        omni_model="minimax-cn/MiniMax-M3",
    )
    with pytest.raises(ValueError, match="OMNIROUTE_BASE_URL, OMNIROUTE_API_KEY"):
        cli.make_runtime(tmp_path, settings, "openai")
