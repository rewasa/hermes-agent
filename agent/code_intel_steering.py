"""Steer agents toward code_intel tools when they use generic file tools on source code.

Appends lightweight hints to tool results when the agent uses read_file, search_files,
or patch on paths that would be better handled by code_symbols, code_search, or
code_refactor respectively.

This is a soft nudge — it never blocks or redirects, just reminds the model that
a more efficient tool exists for the current task. The hints are short (~1-2 lines)
and only fire when the target path is a recognized source code file.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# Source code extensions supported by tree-sitter / ast-grep
_SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".rs", ".go", ".java", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
}

# Only nudge once per tool+path combination per session to avoid spamming
_MAX_NUDGE_PER_TOOL = 3


def _is_source_path(path: str) -> bool:
    """Check if a path points to a source code file we can analyze with tree-sitter."""
    ext = Path(path).suffix.lower()
    return ext in _SOURCE_EXTENSIONS


def _is_source_dir(path: str) -> bool:
    """Check if a directory likely contains source code (heuristic: has source files)."""
    p = Path(path)
    if not p.is_dir():
        return False
    # Quick check: any source file in top-level directory
    try:
        for child in p.iterdir():
            if child.is_file() and child.suffix.lower() in _SOURCE_EXTENSIONS:
                return True
    except (OSError, PermissionError):
        pass
    return False


class CodeIntelSteering:
    """Track tool usage and emit steering hints for code_intel tools.

    Usage::

        steering = CodeIntelSteering()

        # After each tool call, before appending to messages:
        hint = steering.check_tool_call("read_file", {"path": "src/main.py"})
        if hint:
            function_result += hint
    """

    def __init__(self):
        self._nudge_counts: Dict[str, int] = {}

    def check_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        available_tools: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """Check if a tool call should trigger a code_intel steering hint.

        Args:
            tool_name: Name of the tool being called.
            tool_args: Arguments passed to the tool.
            available_tools: Set of available tool names (to check if code_intel
                tools are actually loaded). If None, assumes they're available.

        Returns:
            Hint string to append to tool result, or None.
        """
        if available_tools is not None:
            has_intel = bool({"code_symbols", "code_search", "code_refactor"} & available_tools)
            if not has_intel:
                return None

        path = tool_args.get("path", "")

        if tool_name == "read_file" and _is_source_path(path):
            return self._maybe_nudge("read_file", path,
                "💡 Tip: For navigating source code (list functions, classes, methods), "
                "use code_symbols — it returns signatures with line numbers using far fewer tokens."
            )

        if tool_name == "search_files" and (tool_args.get("target") == "content" or "target" not in tool_args):
            # Only nudge for content search, not file-finding
            pattern = tool_args.get("pattern", "")
            search_path = tool_args.get("path", ".")
            if pattern and (_is_source_path(search_path) or _is_source_dir(search_path)):
                return self._maybe_nudge("search_files", search_path,
                    "💡 Tip: For structural source-code search (function calls, imports, decorators), "
                    "use code_search — AST-aware and won't match comments or strings."
                )

        if tool_name == "patch":
            if _is_source_path(path):
                return self._maybe_nudge("patch", path,
                    "💡 Tip: For structural refactoring (rename patterns, wrap functions, add parameters), "
                    "use code_refactor — matches by AST structure, not raw text."
                )
            if _is_source_dir(path):
                return self._maybe_nudge("patch_dir", path,
                    "💡 Tip: For bulk structural refactoring across multiple files, "
                    "use code_refactor with a directory path — it recursively refactors all source files."
                )

        return None

    def _maybe_nudge(self, key: str, path: str, hint: str) -> Optional[str]:
        """Rate-limit nudges to avoid spamming the model."""
        # Track per tool type, not per individual path
        count = self._nudge_counts.get(key, 0)
        if count >= _MAX_NUDGE_PER_TOOL:
            return None
        self._nudge_counts[key] = count + 1
        return "\n\n" + hint
