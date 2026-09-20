from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platform_v2.tools.github_publish_system.sync import rewrite_links_for_github_pages, sync_frontend


def test_sync_frontend_does_not_use_delete_by_default(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("platform_v2.tools.github_publish_system.sync.subprocess.run", side_effect=fake_run) as run_mock:
        sync_frontend(source=source, dest=dest, dry_run=False)

    called_cmd = run_mock.call_args.args[0]
    assert called_cmd[0] == "rsync"
    assert "--delete" not in called_cmd
    assert called_cmd[-2:] == [f"{source}/", f"{dest}/"]


def test_publish_rewrite_replaces_retired_github_domain(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<link rel="canonical" href="https://sandroabashishvili.github.io/Bitcoin-Live-Signals/spot/">',
        encoding="utf-8",
    )

    rewrite_links_for_github_pages(pages_repo=tmp_path, dry_run=False)

    rendered = page.read_text(encoding="utf-8")
    assert "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/" in rendered
    assert "sandroabashishvili.github.io" not in rendered
