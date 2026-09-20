from __future__ import annotations

from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = WORKSPACE_ROOT
DEFAULT_BACKUP_ROOT = WORKSPACE_ROOT.parent / "SmartSignalHub_backups"
DEFAULT_PROJECT_NAME = "SmartSignalHub_V2"
DEFAULT_USB_PATH = "/mnt/d"
DEFAULT_FLASH_PATH = "/mnt/f"
LOG_DIR = DEFAULT_BACKUP_ROOT / "logs"
LOG_FILE = LOG_DIR / "backup_log.txt"
MANIFEST_NAME = "manifest.json"
ZIP_SUFFIX = ".zip"
HOME_ROOT = WORKSPACE_ROOT.parent
HOME_CRITICAL_BACKUP_ROOT = HOME_ROOT / "Sandro_home_backups"
HOME_CRITICAL_PROJECT_NAME = "Sandro_Home_Critical"
MIGRATION_PRIVATE_BACKUP_ROOT = HOME_ROOT / "Sandro_migration_private_backups"
MIGRATION_PRIVATE_PROJECT_NAME = "Sandro_WSL_Migration_Private"
WINDOWS_USER_ROOT = Path("/mnt/c/Users/Admin")
WINDOWS_CRITICAL_BACKUP_ROOT = HOME_ROOT / "Windows_user_critical_backups"
WINDOWS_CRITICAL_PROJECT_NAME = "Windows_User_Critical"
DEFAULT_EXCLUDES = {
    "__pycache__/",
    "*.pyc",
    ".mypy_cache/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    ".env",
    "**/.env",
    ".DS_Store",
    "venv/**",
    "myenv/**",
    ".git/",
    ".git/**",
    ".git",
    "**/.git",
    "**/.git/",
    "**/.git/**",
    "backups/**",
    "SmartSignalHub_backups/**",
    "platform_v2/public_site/assets/news/**",
    "publish/**",
    "platform_v2/runtime/database/*.sqlite3",
    "platform_v2/runtime/database/*.sqlite3-wal",
    "platform_v2/runtime/database/*.sqlite3-shm",
}

HOME_CRITICAL_INCLUDES = {
    "# SmartSignalHub AI Assistant — Vis.txt",
    "CODEX_MASTER_CONTEXT.md",
    "SV SANDRO/**",
    "Screenshot/**",
    "docs/**",
    "docs_archive_platform_v2/**",
    "portfolio_projects/**",
    "research_snapshots/**",
    "terminal_commands_reference.md",
    "ტექნიკური მონაცემები.txt",
}

SMARTSIGNALHUB_REQUIRED_PATHS = (
    "platform_v2",
    "platform_v2/requirements.txt",
)

HOME_CRITICAL_REQUIRED_PATHS = (
    "docs/00_MASTER_PLAN.md",
    "docs/terminal_commands_reference.md",
    "portfolio_projects",
    "research_snapshots",
)

MIGRATION_PRIVATE_INCLUDES = HOME_CRITICAL_INCLUDES | {
    ".bash_history",
    ".codex/**",
    ".config/**",
    ".git-credentials",
    ".gitconfig",
    ".python_history",
    ".ssh/**",
    "SmartSignalHub/.env",
    "runtime_archives/**",
}

MIGRATION_PRIVATE_REQUIRED_PATHS = (
    "docs/00_MASTER_PLAN.md",
    "portfolio_projects",
    "runtime_archives",
    ".codex/sessions",
    ".ssh/id_ed25519",
    ".gitconfig",
    ".git-credentials",
    "SmartSignalHub/.env",
)

WINDOWS_CRITICAL_INCLUDES = {
    ".codex/**",
    "AppData/Roaming/Code/User/History/**",
    "AppData/Roaming/Code/User/globalStorage/**",
    "AppData/Roaming/Code/User/keybindings.json",
    "AppData/Roaming/Code/User/profiles/**",
    "AppData/Roaming/Code/User/settings.json",
    "AppData/Roaming/Code/User/snippets/**",
    "AppData/Roaming/Code/User/sync/**",
    "Desktop/**",
    "Documents/**",
    "Downloads/**",
    "Music/**",
    "OneDrive/**",
    "Pictures/**",
    "Videos/**",
}

WINDOWS_CRITICAL_REQUIRED_PATHS = (
    ".codex/sessions",
    ".codex/auth.json",
    "Desktop",
    "Downloads",
)

# The final migration archive intentionally preserves private authentication and
# Git metadata. These default safety exclusions remain active for normal backups.
MIGRATION_ALLOWED_EXCLUDE_OVERRIDES = {
    ".env",
    "**/.env",
    ".git/",
    ".git/**",
    ".git",
    "**/.git",
    "**/.git/",
    "**/.git/**",
}

HOME_CRITICAL_EXCLUDES = {
    ".agents",
    ".agents/**",
    ".antigravity-server",
    ".antigravity-server/**",
    ".bash_history",
    ".cache",
    ".cache/**",
    ".claude",
    ".claude/**",
    ".claude.json",
    ".codex",
    ".codex/**",
    ".config",
    ".config/**",
    ".copilot",
    ".copilot/**",
    ".dotnet",
    ".dotnet/**",
    ".gemini",
    ".gemini/**",
    ".git",
    ".git/**",
    ".git-credentials",
    ".gitconfig",
    ".landscape",
    ".landscape/**",
    ".local",
    ".local/**",
    ".npm",
    ".npm/**",
    ".ollama",
    ".ollama/**",
    ".python_history",
    ".ssh",
    ".ssh/**",
    ".sudo_as_admin_successful",
    ".vscode-server",
    ".vscode-server/**",
    "SmartSignalHub",
    "SmartSignalHub/**",
    "SmartSignalHub_backups",
    "SmartSignalHub_backups/**",
    "Sandro_home_backups",
    "Sandro_home_backups/**",
    "runtime_archives",
    "runtime_archives/**",
    "ta-lib",
    "ta-lib/**",
    "ta-lib-0.4.0-src.tar.gz",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/.codex",
    "**/.codex/**",
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/node_modules/**",
    "**/lighthouse-profile/**",
    "portfolio_projects/quality_system/artifacts/**",
}

MIGRATION_PRIVATE_EXCLUDES = HOME_CRITICAL_EXCLUDES - {
    ".bash_history",
    ".codex",
    ".codex/**",
    ".config",
    ".config/**",
    ".git",
    ".git/**",
    ".git-credentials",
    ".gitconfig",
    ".python_history",
    ".ssh",
    ".ssh/**",
    "SmartSignalHub",
    "SmartSignalHub/**",
    "runtime_archives",
    "runtime_archives/**",
    "**/.codex",
    "**/.codex/**",
    "**/.git/**",
}
