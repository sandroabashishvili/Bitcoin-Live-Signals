"""Compatibility entrypoint; implementation lives in local workspace_tools."""
from pathlib import Path
import os
import sys

_tools = Path(os.environ.get("WORKSPACE_TOOLS_ROOT", Path.home() / "workspace_tools"))
_package = _tools / "ai_assistant" / "ai_assistant"
if not _package.is_dir():
    raise ImportError("Restore workspace_tools/ai_assistant from your private backup; see workspace_tools/README.md")
sys.path.insert(0, str(_package.parent))
__path__ = [str(_package)]
