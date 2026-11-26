from argparse import Namespace

import pytest

from sandbox_producthunt import cli


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
