from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublishConfig:
    repo_root: Path
    pages_repo: Path
    repo_url: str
    branch: str
    dry_run: bool
    full_sync: bool
    stats: bool
    commit: bool
    push: bool
    commit_message: str | None
    amend: bool = False

    @property
    def public_site_source(self) -> Path:
        return self.repo_root / "public_site"

    @property
    def public_site_dest(self) -> Path:
        return self.pages_repo

    @property
    def spot_dashboard_source(self) -> Path:
        return self.repo_root / "spot" / "dashboard"

    @property
    def spot_dashboard_dest(self) -> Path:
        return self.pages_repo / "spot" / "dashboard"

    @property
    def futures_dashboard_source(self) -> Path:
        return self.repo_root / "futures" / "dashboard"

    @property
    def futures_dashboard_dest(self) -> Path:
        return self.pages_repo / "futures" / "dashboard"

    @property
    def hedge_dashboard_source(self) -> Path:
        return self.repo_root / "futures_hedge" / "dashboard"

    @property
    def hedge_dashboard_dest(self) -> Path:
        return self.pages_repo / "futures_hedge" / "dashboard"

    @property
    def shared_frontend_source(self) -> Path:
        return self.repo_root / "shared" / "frontend"

    @property
    def shared_frontend_dest(self) -> Path:
        return self.pages_repo / "shared"
