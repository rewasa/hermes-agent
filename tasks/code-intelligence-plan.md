# Native Code Intelligence for Hermes Agent

## Problem Statement

Hermes currently lacks semantic code understanding. The existing tools are:
- `search_files` — regex/ripgrep text search (no AST awareness)
- `read_file` — raw line-by-line reading (no symbol extraction)
- `patch` — fuzzy text replacement (no structural guarantees)
- `execute_code` — Python sandbox (no code analysis primitives)

This means the agent must read entire files and relies on regex for code navigation.
Result: **wasted tokens, imprecise refactoring, no cross-reference tracing**.

## Research Summary

### Evaluated Approaches

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **LSP MCP Server** | Full type info, diagnostics, references | Complex setup, language servers as deps, slow startup, fragile | ❌ Rejected (user confirmed) |
| **ast-grep CLI** | Blazing fast, structural search/replace, multi-lang, Python API | External binary dep, no symbol indexing | ⚠️ Partial |
| **ast-grep Python API** | Programmatic AST search/replace in-process | No cross-file indexing, limited language detection | ⚠️ Core engine |
| **tree-sitter Python** | Fast parsing, query language, 20+ langs | Low-level, no search/replace primitives | ✅ Foundation |
| **code-analyze-mcp** | 59% token savings benchmark, call graphs | External MCP server, Python | ❌ External dependency |
| **code-graph-mcp** | Knowledge graph, semantic search, impact analysis | Go binary, external | ❌ External dependency |
| **Lumora** | Rust single binary, 21 tools, offline | External binary | ❌ External dependency |

### Key Insight

The benchmarks show **46-68% token savings** from AST-aware code intelligence.
We can achieve this **natively** by embedding tree-sitter + ast-grep-py directly
into Hermes tools — zero external servers, zero MCP overhead.

## Design: Native `code_intel` Toolset

### Architecture

```
tools/code_intel.py
├── tree-sitter parsing (Python bindings)
├── ast-grep-py for structural search/replace
├── Lightweight symbol index (SQLite, per-project)
└── Hermes tool registry integration
```

### Three New Tools

#### 1. `code_symbols` — Symbol Intelligence

**What it does:** Extract and search symbols (functions, classes, methods, interfaces,
types, enums) from source files without reading raw content.

**Schema:**
```python
{
    "name": "code_symbols",
    "description": "Extract symbols from source files using AST parsing. "
        "Returns function/class/method signatures with line ranges. "
        "Token-efficient alternative to reading entire files. "
        "Supports Python, TypeScript, JavaScript, Rust, Go, Java, and more.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory path"},
            "pattern": {"type": "string", "description": "Fuzzy symbol name filter (optional)"},
            "kind": {"type": "string", "enum": ["all", "function", "class", "method", "interface", "type", "variable"],
                     "description": "Filter by symbol kind (default: all)"},
            "include_body": {"type": "boolean", "description": "Include function/method bodies (default: false)"},
            "language": {"type": "string", "description": "Override language detection (auto-detected from extension)"}
        },
        "required": ["path"]
    }
}
```

**Example output:**
```
src/model_tools.py (562 lines)
  L196  get_tool_definitions(enabled_toolsets, disabled_toolsets, quiet_mode) -> List[Dict]
  L334  coerce_tool_args(tool_name, args) -> Dict
  L380  handle_function_call(tool_name, tool_args, ...) -> str
```

**Token savings:** ~80-95% vs reading full file for navigation.

#### 2. `code_search` — Structural/AST Search

**What it does:** Search code by AST structure, not just text. Finds patterns
like "all async function calls", "all class methods that return a specific type",
"all decorators with a specific argument".

**Schema:**
```python
{
    "name": "code_search",
    "description": "AST-aware code search using tree-sitter patterns. "
        "Search by code structure, not just text. Find function calls, "
        "class definitions, import patterns, decorator usage, etc. "
        "Returns matches with file:line:col and context.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Tree-sitter query or structural pattern"},
            "path": {"type": "string", "description": "Directory to search (default: .)"},
            "file_glob": {"type": "string", "description": "Filter files (e.g., '*.py', '*.ts')"},
            "language": {"type": "string", "description": "Language for the pattern"},
            "context_lines": {"type": "integer", "description": "Context lines around matches (default: 2)",
                             "default": 2},
            "max_results": {"type": "integer", "description": "Max matches (default: 50)", "default": 50}
        },
        "required": ["pattern"]
    }
}
```

**Example:** `code_search(pattern="registry.register(", file_glob="*.py")`
→ Returns all `registry.register()` calls with their arguments and context.

#### 3. `code_refactor` — Structural Code Transformation

**What it does:** Perform AST-safe code transformations. Replaces code by structure,
not by text matching. Guaranteed to produce syntactically valid output.

**Schema:**
```python
{
    "name": "code_refactor",
    "description": "AST-based structural code search and replace. "
        "Transform code patterns across files using tree-sitter/ast-grep. "
        "Unlike patch (text-based), this understands code structure — "
        "finds patterns regardless of formatting differences. "
        "Dry-run mode shows preview without modifying files.",
    "parameters": {
        "type": "object",
        "properties": {
            "find_pattern": {"type": "string", "description": "AST pattern to match (ast-grep syntax)"},
            "rewrite_pattern": {"type": "string", "description": "Replacement pattern ($META_VARS from find)"},
            "path": {"type": "string", "description": "File or directory"},
            "file_glob": {"type": "string", "description": "Filter files (e.g., '*.ts')"},
            "language": {"type": "string", "description": "Language (auto-detected)"},
            "dry_run": {"type": "boolean", "description": "Preview changes without writing (default: true)",
                        "default": true}
        },
        "required": ["find_pattern", "rewrite_pattern", "path"]
    }
}
```

**Example:** `code_refactor(find_pattern="console.log($A)", rewrite_pattern="logger.info($A)", path="src/", file_glob="*.ts")`
→ Structurally finds all `console.log(...)` and replaces with `logger.info(...)`.

### Language Support (Priority Order)

| Language | File Extensions | tree-sitter Package |
|----------|----------------|---------------------|
| Python | `.py` | `tree-sitter-python` |
| TypeScript | `.ts`, `.tsx` | `tree-sitter-typescript` |
| JavaScript | `.js`, `.jsx`, `.mjs` | `tree-sitter-javascript` |
| Rust | `.rs` | `tree-sitter-rust` |
| Go | `.go` | `tree-sitter-go` |
| Java | `.java` | `tree-sitter-java` |
| C/C++ | `.c`, `.cpp`, `.h` | `tree-sitter-c`, `tree-sitter-cpp` |

### Dependencies

```
# New Python deps (all pure-Python with precompiled wheels)
tree-sitter>=0.24.0          # Core parsing library
tree-sitter-python>=0.23.0   # Python grammar
tree-sitter-javascript>=0.23.0  # JS grammar
tree-sitter-typescript>=0.23.0  # TS/TSX grammar
tree-sitter-rust>=0.23.0     # Rust grammar
tree-sitter-go>=0.23.0       # Go grammar
tree-sitter-java>=0.23.0     # Java grammar
ast-grep-py>=0.37.0          # Structural search/replace
```

### Integration Points

1. **`toolsets.py`** — Add `"code_intel"` toolset with `code_symbols`, `code_search`, `code_refactor`
2. **`_HERMES_CORE_TOOLS`** — Add the 3 tools to core list
3. **`platform_toolsets`** — Already covered via `_HERMES_CORE_TOOLS`
4. **`file_tools.py`** — Cross-reference from `read_file` description: "For symbol-level
   understanding, prefer `code_symbols` over reading entire files."

## Implementation Plan

### Phase 1: Foundation (Day 1)
- [ ] Install dependencies in venv
- [ ] Create `tools/code_intel.py` with tree-sitter language detection
- [ ] Implement `code_symbols` tool (symbol extraction)
- [ ] Register tools in toolset
- [ ] Write basic tests

### Phase 2: Structural Search (Day 1-2)
- [ ] Implement `code_search` (tree-sitter query-based search)
- [ ] Add high-level pattern shortcuts (function calls, class definitions, imports)
- [ ] Benchmark against `search_files` for token usage

### Phase 3: Structural Refactor (Day 2)
- [ ] Integrate ast-grep-py for `code_refactor`
- [ ] Implement dry-run mode with diff preview
- [ ] Add multi-file refactor support
- [ ] Safety: validate output is syntactically valid before writing

### Phase 4: Polish & Optimization
- [ ] Update `read_file` description to guide models toward `code_symbols`
- [ ] Update `search_files` description for code-aware alternatives
- [ ] Add symbol caching for repeated queries within a session
- [ ] Integration tests with Hermes test suite
- [ ] Update SKILL.md with code intelligence patterns

## Expected Impact

| Metric | Current | With code_intel |
|--------|---------|-----------------|
| Symbols per token (navigation) | ~50 lines = ~2K tokens | ~20 symbols = ~200 tokens (10x) |
| Pattern search precision | Regex (many false positives) | AST-aware (structural) |
| Refactoring safety | Text-based fuzzy matching | AST-guaranteed syntactic validity |
| Cross-file refactoring | Manual grep+patch loop | Single `code_refactor` call |
| External dependencies | None | None (all in-process Python) |
