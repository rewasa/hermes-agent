#!/usr/bin/env python3
"""
Code Intelligence Tools Module

AST-aware code analysis tools using tree-sitter and ast-grep.
Provides structural symbol extraction, pattern search, and safe refactoring.

Token-efficient alternative to reading entire files for code navigation.
"""

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry — maps file extensions → tree-sitter Language objects
# Lazy-loaded on first use to avoid slow imports at module level.
# ---------------------------------------------------------------------------

_LANG_LOCK = threading.Lock()
_LANG_CACHE: Dict[str, object] = {}  # ext → Language
_PARSER_CACHE: Dict[str, object] = {}  # lang_key → Parser
_LANG_READY = False

# Extension → language key mapping
_EXT_TO_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

# Supported languages for ast-grep (subset — only those with grammars)
_AST_GRASP_LANGS = {
    "python", "javascript", "typescript", "tsx", "rust", "go", "java", "c", "cpp",
}

# ---------------------------------------------------------------------------
# tree-sitter symbol queries per language
# ---------------------------------------------------------------------------

_SYMBOL_QUERIES = {
    "python": """
        ; Functions (sync and async)
        (function_definition
            name: (identifier) @name
        ) @def

        ; Classes
        (class_definition
            name: (identifier) @name
        ) @def

        ; Class methods
        (class_definition
            body: (block
                (function_definition
                    "async"? @keyword
                    name: (identifier) @name
                ) @def
            )
        )

        ; Module-level assignments that look like constants (UPPER_CASE)
        (assignment
            left: (identifier) @name
        ) @constant

        ; Decorated functions/classes
        (decorated_definition
            definition: (function_definition
                "async"? @keyword
                name: (identifier) @name
            ) @def
        )

        (decorated_definition
            definition: (class_definition
                name: (identifier) @name
            ) @def
        )
    """,
    "typescript": """
        ; Functions (sync and async)
        (function_declaration
            name: (identifier) @name
        ) @def

        ; Arrow functions assigned to variables (const/let)
        (lexical_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        ; Arrow functions assigned to variables (var)
        (variable_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        ; Classes
        (class_declaration
            name: (type_identifier) @name
        ) @def

        ; Interfaces
        (interface_declaration
            name: (type_identifier) @name
        ) @def

        ; Type aliases
        (type_alias_declaration
            name: (type_identifier) @name
        ) @def

        ; Enums
        (enum_declaration
            name: (identifier) @name
        ) @def

        ; Export statements wrapping the above
        (export_statement
            (function_declaration
                name: (identifier) @name
            ) @def
        )

        (export_statement
            (class_declaration
                name: (type_identifier) @name
            ) @def
        )

        (export_statement
            (interface_declaration
                name: (type_identifier) @name
            ) @def
        )

        ; Class methods
        (class_declaration
            body: (class_body
                (method_definition
                    name: (property_identifier) @name
                ) @def
            )
        )
    """,
    "tsx": """
        ; Same as typescript plus component detection
        ; Functions (sync and async)
        (function_declaration
            name: (identifier) @name
        ) @def

        ; Arrow functions (const/let)
        (lexical_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        ; Arrow functions (var)
        (variable_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        (class_declaration
            name: (type_identifier) @name
        ) @def

        (interface_declaration
            name: (type_identifier) @name
        ) @def

        (type_alias_declaration
            name: (type_identifier) @name
        ) @def

        (export_statement
            (function_declaration
                name: (identifier) @name
            ) @def
        )

        (export_statement
            (class_declaration
                name: (type_identifier) @name
            ) @def
        )

        (export_statement
            (interface_declaration
                name: (type_identifier) @name
            ) @def
        )

        (class_declaration
            body: (class_body
                (method_definition
                    name: (property_identifier) @name
                ) @def
            )
        )
    """,
    "javascript": """
        ; Functions (sync and async — async is a keyword child, handled automatically)
        (function_declaration
            name: (identifier) @name
        ) @def

        ; Arrow functions (const/let)
        (lexical_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        ; Arrow functions (var)
        (variable_declaration
            (variable_declarator
                name: (identifier) @name
                value: (arrow_function) @arrow
            )
        )

        ; Classes
        (class_declaration
            name: (identifier) @name
        ) @def

        ; Class methods
        (class_declaration
            body: (class_body
                (method_definition
                    name: (property_identifier) @name
                ) @def
            )
        )

        ; Export statements
        (export_statement
            (function_declaration
                name: (identifier) @name
            ) @def
        )

        (export_statement
            (class_declaration
                name: (identifier) @name
            ) @def
        )
    """,
    "rust": """
        ; Functions (matches both sync and async — async is a function_modifiers child)
        (function_item
            name: (identifier) @name
        ) @def

        ; Structs
        (struct_item
            name: (type_identifier) @name
        ) @def

        ; Enums
        (enum_item
            name: (type_identifier) @name
        ) @def

        ; Traits
        (trait_item
            name: (type_identifier) @name
        ) @def

        ; impl blocks — methods
        (impl_item
            body: (declaration_list
                (function_item
                    name: (identifier) @name
                ) @def
            )
        )

        ; impl blocks for traits
        (impl_item
            trait: (type_identifier) @trait_name
            type: (type_identifier) @impl_for
            body: (declaration_list
                (function_item
                    name: (identifier) @name
                ) @def
            )
        )

        ; Constants
        (const_item
            name: (identifier) @name
        ) @constant

        ; Type aliases
        (type_item
            name: (type_identifier) @name
        ) @def

        ; Mods
        (mod_item
            name: (identifier) @name
        ) @def
    """,
    "go": """
        ; Functions
        (function_declaration
            name: (identifier) @name
        ) @def

        ; Methods (receiver functions)
        (method_declaration
            name: (field_identifier) @name
        ) @def

        ; Structs
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (struct_type)
            )
        ) @def

        ; Interfaces
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (interface_type)
            )
        ) @def

        ; Type aliases
        (type_declaration
            (type_spec
                name: (type_identifier) @name
            )
        ) @def

        ; Variables
        (var_declaration
            (var_spec
                name: (identifier) @name
            )
        ) @constant
    """,
    "java": """
        ; Classes
        (class_declaration
            name: (identifier) @name
        ) @def

        ; Interfaces
        (interface_declaration
            name: (identifier) @name
        ) @def

        ; Enums
        (enum_declaration
            name: (identifier) @name
        ) @def

        ; Methods
        (class_declaration
            body: (class_body
                (method_declaration
                    name: (identifier) @name
                ) @def
            )
        )

        ; Fields
        (class_declaration
            body: (class_body
                (field_declaration
                    (variable_declarator
                        name: (identifier) @name
                    )
                ) @field
            )
        )
    """,
}

# Node types that indicate specific symbol kinds
_NODE_KIND_MAP = {
    "function_definition": "function",
    "function_declaration": "function",
    "function_item": "function",
    "arrow_function": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
    "enum_item": "enum",
    "struct_item": "struct",
    "struct_type": "struct",
    "interface_type": "interface",
    "trait_item": "trait",
    "type_item": "type",
    "type_alias": "type",
    "type_spec": "type",
    "method_definition": "method",
    "method_declaration": "method",
    "impl_item": "impl",
    "mod_item": "module",
    "assignment": "variable",
    "variable_declaration": "variable",
    "const_item": "constant",
    "constant_item": "constant",
    "var_declaration": "variable",
    "var_spec": "variable",
    "field_declaration": "field",
}


def _init_languages():
    """Load all language grammars. Thread-safe, runs once."""
    global _LANG_READY, _LANG_CACHE
    with _LANG_LOCK:
        if _LANG_READY:
            return

        try:
            import tree_sitter_python as tspython
            import tree_sitter_javascript as tsjs
            import tree_sitter_typescript as tsts
            import tree_sitter_rust as tsrust
            import tree_sitter_go as tsgo
            import tree_sitter_java as tsjava
            from tree_sitter import Language
        except ImportError as e:
            logger.warning("Code intelligence deps not installed: %s", e)
            return

        langs = {
            "python": Language(tspython.language()),
            "javascript": Language(tsjs.language()),
            "typescript": Language(tsts.language_typescript()),
            "tsx": Language(tsts.language_tsx()),
            "rust": Language(tsrust.language()),
            "go": Language(tsgo.language()),
            "java": Language(tsjava.language()),
        }

        _LANG_CACHE.update(langs)
        _LANG_READY = True


def _get_language(lang_key: str):
    """Get a tree-sitter Language by key, lazy-loading if needed."""
    if not _LANG_READY:
        _init_languages()
    return _LANG_CACHE.get(lang_key)


def _get_parser(lang_key: str):
    """Get or create a cached tree-sitter Parser for a language."""
    if not _LANG_READY:
        _init_languages()

    if lang_key not in _PARSER_CACHE:
        lang = _LANG_CACHE.get(lang_key)
        if lang is None:
            return None
        from tree_sitter import Parser
        parser = Parser(lang)
        _PARSER_CACHE[lang_key] = parser

    return _PARSER_CACHE[lang_key]


def detect_language(path: str, explicit_lang: Optional[str] = None) -> Optional[str]:
    """Detect language from file extension or explicit override."""
    if explicit_lang:
        return explicit_lang.lower()

    ext = Path(path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


def _classify_node(node, query_capture_name: str) -> str:
    """Classify a tree-sitter node into a symbol kind."""
    # Check the capture name first
    if query_capture_name == "name":
        # Classify by parent or sibling context
        pass

    # Check node type directly
    kind = _NODE_KIND_MAP.get(node.type)
    if kind:
        return kind

    return "symbol"


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------

def extract_symbols(
    source: bytes,
    lang_key: str,
    pattern_filter: Optional[str] = None,
    kind_filter: Optional[str] = None,
    include_body: bool = False,
) -> List[dict]:
    """Extract symbols from source code using tree-sitter queries.

    Returns a list of dicts with keys:
        - name: symbol name
        - kind: function, class, method, interface, type, enum, struct, trait, etc.
        - line: start line (1-indexed)
        - end_line: end line (1-indexed)
        - signature: first line text
        - body: source text of the body (if include_body=True)
    """
    from tree_sitter import Query, QueryCursor

    parser = _get_parser(lang_key)
    lang = _get_language(lang_key)
    if parser is None or lang is None:
        return []

    tree = parser.parse(source)
    query_text = _SYMBOL_QUERIES.get(lang_key)
    if not query_text:
        # Fallback: generic query for common definitions
        query_text = """
            (function_definition name: (identifier) @name) @def
            (class_definition name: (identifier) @name) @def
            (function_declaration name: (identifier) @name) @def
            (class_declaration name: (type_identifier) @name) @def
        """

    try:
        query = Query(lang, query_text)
    except Exception as e:
        logger.debug("Query compile error for %s: %s", lang_key, e)
        return []

    # tree-sitter 0.25+: use QueryCursor.matches() which returns
    # (pattern_index, {capture_name: [Node, ...], ...}) tuples
    qc = QueryCursor(query)
    seen: set = set()
    symbols: List[dict] = []

    source_lines = source.split(b"\n")

    for _pattern_idx, captures_dict in qc.matches(tree.root_node):
        # Each match should have at minimum a "name" capture and a "def" capture.
        # We use "def" for the full definition extent and "name" for the identifier.
        name_nodes = captures_dict.get("name", [])
        def_nodes = (
            captures_dict.get("def")
            or captures_dict.get("constant")
            or captures_dict.get("field")
            or captures_dict.get("arrow")
        )

        if not name_nodes:
            continue

        # Take the first name node (some patterns have multiple via alternation)
        name_node = name_nodes[0]
        name_text = name_node.text.decode("utf-8", errors="replace")

        # Determine the definition node extent
        if def_nodes:
            def_node = def_nodes[0]
        else:
            # Fallback: use the parent of the name node
            def_node = name_node.parent
            if def_node is None:
                continue

        # Dedup by (name, start_row)
        key = (name_text, def_node.start_point[0])
        if key in seen:
            continue
        seen.add(key)

        # Determine symbol kind from node type
        kind = _NODE_KIND_MAP.get(def_node.type, "symbol")

        # For Go type_spec: detect struct/interface/trait by looking at the type child
        if def_node.type == "type_spec" and kind == "symbol":
            for child in def_node.children:
                child_kind = _NODE_KIND_MAP.get(child.type)
                if child_kind in ("struct", "interface"):
                    kind = child_kind
                    break

        # Detect methods (function inside class/impl/struct body)
        parent_of_def = def_node.parent
        if parent_of_def:
            gp = parent_of_def.parent
            if parent_of_def.type == "block" and gp and gp.type == "class_definition":
                if kind == "function":
                    kind = "method"
            elif parent_of_def.type in ("class_body", "declaration_list"):
                if gp and gp.type in (
                    "class_declaration", "class_definition",
                    "impl_item", "struct_item",
                ):
                    if kind == "function":
                        kind = "method"

        # Apply kind filter
        if kind_filter and kind_filter != "all":
            if kind != kind_filter:
                continue

        # Apply pattern filter (fuzzy substring match)
        if pattern_filter:
            if pattern_filter.lower() not in name_text.lower():
                continue

        start_line = def_node.start_point[0] + 1  # 1-indexed
        end_line = def_node.end_point[0] + 1
        sig_start = def_node.start_point[0]
        sig_end = min(def_node.end_point[0], sig_start + 2)  # first 3 lines max
        signature = b"\n".join(source_lines[sig_start:sig_end]).decode("utf-8", errors="replace").strip()

        sym = {
            "name": name_text,
            "kind": kind,
            "line": start_line,
            "end_line": end_line,
            "signature": signature,
        }

        if include_body:
            sym["body"] = source[def_node.start_byte:def_node.end_byte].decode("utf-8", errors="replace")

        symbols.append(sym)

    # Sort by line number
    symbols.sort(key=lambda s: s["line"])
    return symbols


def _format_symbols_output(
    file_path: str,
    symbols: List[dict],
    total_lines: int,
    lang_key: str,
) -> str:
    """Format extracted symbols into a compact, token-efficient string."""
    if not symbols:
        return json.dumps({
            "path": file_path,
            "language": lang_key,
            "total_lines": total_lines,
            "symbols": [],
            "message": "No symbols found. File may be empty or language not supported.",
        })

    lines = []
    lines.append(f"{file_path} ({total_lines} lines, {lang_key})")

    # Group by kind for readability
    current_kind = None
    for sym in symbols:
        if sym["kind"] != current_kind:
            current_kind = sym["kind"]
            lines.append(f"  [{current_kind}]")
        sig = sym["signature"]
        # Truncate long signatures
        if len(sig) > 120:
            sig = sig[:117] + "..."
        lines.append(f"  L{sym['line']:>4d}  {sym['name']}  {sig}")

    return json.dumps({
        "path": file_path,
        "language": lang_key,
        "total_lines": total_lines,
        "symbol_count": len(symbols),
        "symbols": symbols,
        "formatted": "\n".join(lines),
    })


# ---------------------------------------------------------------------------
# code_symbols tool implementation
# ---------------------------------------------------------------------------

def code_symbols_tool(
    path: str,
    pattern: Optional[str] = None,
    kind: Optional[str] = None,
    include_body: bool = False,
    language: Optional[str] = None,
) -> str:
    """Extract symbols from source files using tree-sitter AST parsing."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        return json.dumps({
            "error": f"Path not found: {path}",
        })

    if target.is_dir():
        # Skip language detection for directories — scan all supported files
        lang_key = None
    else:
        lang_key = detect_language(str(target), language)
        if lang_key is None:
            return json.dumps({
                "error": (
                    f"Unsupported language for '{path}'. "
                    f"Supported extensions: {', '.join(sorted(set(_EXT_TO_LANG.values())))}"
                ),
            })

    if target.is_file():
        source = target.read_bytes()
        total_lines = source.count(b"\n") + 1
        symbols = extract_symbols(
            source, lang_key,
            pattern_filter=pattern,
            kind_filter=kind,
            include_body=include_body,
        )
        return _format_symbols_output(str(target), symbols, total_lines, lang_key)

    # Directory: scan all supported files
    results = []
    all_symbols = []
    for ext in _EXT_TO_LANG:
        for file_path in sorted(target.rglob(f"*{ext}")):
            if not file_path.is_file():
                continue
            try:
                source = file_path.read_bytes()
            except (OSError, PermissionError):
                continue
            file_lang = detect_language(str(file_path), language)
            if file_lang is None:
                continue
            syms = extract_symbols(
                source, file_lang,
                pattern_filter=pattern,
                kind_filter=kind,
                include_body=False,  # Never include body for directory scans
            )
            if syms:
                results.append({
                    "path": str(file_path),
                    "language": file_lang,
                    "total_lines": source.count(b"\n") + 1,
                    "symbol_count": len(syms),
                    "symbols": syms,
                })
                for s in syms:
                    s["file"] = str(file_path)
                    all_symbols.append(s)

    if not results:
        return json.dumps({
            "path": str(target),
            "message": "No symbols found in directory scan.",
            "supported_extensions": sorted(set(_EXT_TO_LANG.values())),
        })

    # Build formatted output
    lines = []
    lines.append(f"Directory: {target} ({len(results)} files with symbols)")
    for r in results:
        lines.append(f"\n{r['path']} ({r['total_lines']} lines, {r['language']})")
        for sym in r["symbols"]:
            sig = sym["signature"]
            if len(sig) > 100:
                sig = sig[:97] + "..."
            lines.append(f"  L{sym['line']:>4d}  [{sym['kind']}] {sym['name']}  {sig}")

    return json.dumps({
        "path": str(target),
        "file_count": len(results),
        "total_symbols": len(all_symbols),
        "results": results,
        "formatted": "\n".join(lines),
    })


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

CODE_SYMBOLS_SCHEMA = {
    "name": "code_symbols",
    "description": (
        "Extract symbols (functions, classes, methods, interfaces, types, enums) "
        "from source files using AST parsing. Token-efficient alternative to "
        "reading entire files. Supports Python, TypeScript, JavaScript, Rust, Go, "
        "and Java. Pass a directory to scan all files. Use 'pattern' for fuzzy name filter, "
        "'kind' to filter by symbol type."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory path to extract symbols from"},
            "pattern": {"type": "string", "description": "Fuzzy symbol name filter (optional, substring match)"},
            "kind": {
                "type": "string",
                "enum": ["all", "function", "class", "method", "interface", "type", "enum", "struct", "trait", "constant", "variable", "module"],
                "description": "Filter by symbol kind (default: all)",
            },
            "include_body": {"type": "boolean", "description": "Include function/method body text (default: false, only for single file)"},
            "language": {"type": "string", "description": "Override language auto-detection (e.g. 'python', 'typescript')"},
        },
        "required": ["path"],
    },
}


def _check_code_intel_reqs() -> bool:
    """Check if code intelligence dependencies are installed."""
    try:
        import tree_sitter  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Register tools
# ---------------------------------------------------------------------------

from tools.registry import registry


def _handle_code_symbols(args, **kw):
    return code_symbols_tool(
        path=args.get("path", ""),
        pattern=args.get("pattern"),
        kind=args.get("kind"),
        include_body=args.get("include_body", False),
        language=args.get("language"),
    )


registry.register(
    name="code_symbols",
    toolset="code_intel",
    schema=CODE_SYMBOLS_SCHEMA,
    handler=_handle_code_symbols,
    check_fn=_check_code_intel_reqs,
    emoji="🔍",
)
