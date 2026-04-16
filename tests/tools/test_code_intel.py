"""Tests for tools/code_intel.py — code_symbols_tool."""

import json
import os
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Skip entire module if tree-sitter is not installed
# ---------------------------------------------------------------------------
pytest.importorskip("tree_sitter", reason="tree-sitter not installed")

from tools.code_intel import (
    code_symbols_tool,
    detect_language,
    extract_symbols,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_py(tmp_path):
    """A small Python source file for testing."""
    src = textwrap.dedent("""\
        MY_CONST = 42

        class Greeter:
            \"\"\"Say hello.\"\"\"

            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

            @staticmethod
            def farewell() -> str:
                return "Goodbye!"

        def top_level_fn(x: int) -> int:
            return x * 2

        async def async_fn() -> None:
            pass
    """)
    f = tmp_path / "sample.py"
    f.write_text(src)
    return f


@pytest.fixture()
def tmp_ts(tmp_path):
    """A small TypeScript source file."""
    src = textwrap.dedent("""\
        export interface Animal {
            name: string;
        }

        export class Dog implements Animal {
            constructor(public name: string) {}

            bark(): string {
                return "woof";
            }
        }

        export function createDog(name: string): Dog {
            return new Dog(name);
        }

        const arrowFn = (x: number): number => x + 1;
    """)
    f = tmp_path / "sample.ts"
    f.write_text(src)
    return f


@pytest.fixture()
def tmp_js(tmp_path):
    """A small JavaScript source file."""
    src = textwrap.dedent("""\
        class Counter {
            constructor() { this.count = 0; }
            increment() { this.count++; }
        }

        function reset(counter) { counter.count = 0; }
        const double = (n) => n * 2;
    """)
    f = tmp_path / "sample.js"
    f.write_text(src)
    return f


@pytest.fixture()
def tmp_rs(tmp_path):
    """A small Rust source file."""
    src = textwrap.dedent("""\
        pub struct Point {
            pub x: f64,
            pub y: f64,
        }

        impl Point {
            pub fn new(x: f64, y: f64) -> Self {
                Point { x, y }
            }

            pub fn distance(&self, other: &Point) -> f64 {
                ((self.x - other.x).powi(2) + (self.y - other.y).powi(2)).sqrt()
            }
        }

        pub fn origin() -> Point {
            Point::new(0.0, 0.0)
        }

        pub trait Shape {
            fn area(&self) -> f64;
        }
    """)
    f = tmp_path / "sample.rs"
    f.write_text(src)
    return f


@pytest.fixture()
def tmp_go(tmp_path):
    """A small Go source file."""
    src = textwrap.dedent("""\
        package main

        type Rectangle struct {
            Width  float64
            Height float64
        }

        func (r Rectangle) Area() float64 {
            return r.Width * r.Height
        }

        func NewRectangle(w, h float64) Rectangle {
            return Rectangle{Width: w, Height: h}
        }

        type Stringer interface {
            String() string
        }
    """)
    f = tmp_path / "sample.go"
    f.write_text(src)
    return f


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_python(self, tmp_py):
        assert detect_language(str(tmp_py)) == "python"

    def test_typescript(self, tmp_ts):
        assert detect_language(str(tmp_ts)) == "typescript"

    def test_javascript(self, tmp_js):
        assert detect_language(str(tmp_js)) == "javascript"

    def test_rust(self, tmp_rs):
        assert detect_language(str(tmp_rs)) == "rust"

    def test_go(self, tmp_go):
        assert detect_language(str(tmp_go)) == "go"

    def test_tsx(self, tmp_path):
        f = tmp_path / "app.tsx"
        f.write_text("")
        assert detect_language(str(f)) == "tsx"

    def test_unknown_returns_none(self, tmp_path):
        f = tmp_path / "file.xyz"
        f.write_text("")
        assert detect_language(str(f)) is None

    def test_explicit_override(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("")
        assert detect_language(str(f), explicit_lang="python") == "python"


# ---------------------------------------------------------------------------
# Python symbol extraction
# ---------------------------------------------------------------------------


class TestPythonSymbols:
    def test_finds_class(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        names = [s["name"] for s in result["symbols"]]
        assert "Greeter" in names

    def test_finds_top_level_function(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        names = [s["name"] for s in result["symbols"]]
        assert "top_level_fn" in names

    def test_finds_method(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        kinds = {s["name"]: s["kind"] for s in result["symbols"]}
        assert "greet" in kinds
        assert kinds["greet"] == "method"

    def test_finds_async_fn(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        names = [s["name"] for s in result["symbols"]]
        assert "async_fn" in names

    def test_filter_by_kind_function(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py), kind="function"))
        for s in result["symbols"]:
            assert s["kind"] == "function"

    def test_filter_by_kind_class(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py), kind="class"))
        for s in result["symbols"]:
            assert s["kind"] == "class"

    def test_pattern_filter(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py), pattern="greet"))
        names = [s["name"] for s in result["symbols"]]
        assert "greet" in names
        assert "top_level_fn" not in names

    def test_include_body(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py), include_body=True))
        for s in result["symbols"]:
            if s["name"] == "top_level_fn":
                assert "body" in s
                assert "return x * 2" in s["body"]
                break
        else:
            pytest.fail("top_level_fn not found")

    def test_line_numbers_positive(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        for s in result["symbols"]:
            assert s["line"] >= 1

    def test_language_reported(self, tmp_py):
        result = json.loads(code_symbols_tool(str(tmp_py)))
        assert result["language"] == "python"


# ---------------------------------------------------------------------------
# TypeScript symbol extraction
# ---------------------------------------------------------------------------


class TestTypeScriptSymbols:
    def test_finds_interface(self, tmp_ts):
        result = json.loads(code_symbols_tool(str(tmp_ts)))
        names = [s["name"] for s in result["symbols"]]
        assert "Animal" in names

    def test_finds_class(self, tmp_ts):
        result = json.loads(code_symbols_tool(str(tmp_ts)))
        names = [s["name"] for s in result["symbols"]]
        assert "Dog" in names

    def test_finds_function(self, tmp_ts):
        result = json.loads(code_symbols_tool(str(tmp_ts)))
        names = [s["name"] for s in result["symbols"]]
        assert "createDog" in names

    def test_finds_arrow_function(self, tmp_ts):
        result = json.loads(code_symbols_tool(str(tmp_ts)))
        names = [s["name"] for s in result["symbols"]]
        assert "arrowFn" in names


# ---------------------------------------------------------------------------
# JavaScript symbol extraction
# ---------------------------------------------------------------------------


class TestJavaScriptSymbols:
    def test_finds_class(self, tmp_js):
        result = json.loads(code_symbols_tool(str(tmp_js)))
        names = [s["name"] for s in result["symbols"]]
        assert "Counter" in names

    def test_finds_function(self, tmp_js):
        result = json.loads(code_symbols_tool(str(tmp_js)))
        names = [s["name"] for s in result["symbols"]]
        assert "reset" in names

    def test_finds_arrow_fn(self, tmp_js):
        result = json.loads(code_symbols_tool(str(tmp_js)))
        names = [s["name"] for s in result["symbols"]]
        assert "double" in names


# ---------------------------------------------------------------------------
# Rust symbol extraction
# ---------------------------------------------------------------------------


class TestRustSymbols:
    def test_finds_struct(self, tmp_rs):
        result = json.loads(code_symbols_tool(str(tmp_rs)))
        names = [s["name"] for s in result["symbols"]]
        assert "Point" in names

    def test_finds_trait(self, tmp_rs):
        result = json.loads(code_symbols_tool(str(tmp_rs)))
        kinds = {s["name"]: s["kind"] for s in result["symbols"]}
        assert "Shape" in kinds
        assert kinds["Shape"] == "trait"

    def test_finds_impl_method(self, tmp_rs):
        result = json.loads(code_symbols_tool(str(tmp_rs)))
        names = [s["name"] for s in result["symbols"]]
        assert "new" in names or "distance" in names

    def test_finds_free_function(self, tmp_rs):
        result = json.loads(code_symbols_tool(str(tmp_rs)))
        names = [s["name"] for s in result["symbols"]]
        assert "origin" in names


# ---------------------------------------------------------------------------
# Go symbol extraction
# ---------------------------------------------------------------------------


class TestGoSymbols:
    def test_finds_struct(self, tmp_go):
        result = json.loads(code_symbols_tool(str(tmp_go)))
        names = [s["name"] for s in result["symbols"]]
        assert "Rectangle" in names

    def test_finds_function(self, tmp_go):
        result = json.loads(code_symbols_tool(str(tmp_go)))
        names = [s["name"] for s in result["symbols"]]
        assert "NewRectangle" in names

    def test_finds_interface(self, tmp_go):
        result = json.loads(code_symbols_tool(str(tmp_go)))
        kinds = {s["name"]: s["kind"] for s in result["symbols"]}
        assert "Stringer" in kinds
        # Go interfaces may be classified as interface, type, or symbol depending on grammar
        assert kinds["Stringer"] in ("interface", "type", "symbol")


# ---------------------------------------------------------------------------
# Directory scan
# ---------------------------------------------------------------------------


class TestDirectoryScan:
    def test_scans_multiple_files(self, tmp_path):
        # Create two source files in tmp_path directly
        (tmp_path / "a.py").write_text("def foo(): pass\nclass Bar: pass\n")
        (tmp_path / "b.ts").write_text("export function baz(): void {}\n")
        result = json.loads(code_symbols_tool(str(tmp_path)))
        assert result.get("file_count", 0) >= 2
        assert result.get("total_symbols", 0) > 0

    def test_returns_formatted_string(self, tmp_path):
        (tmp_path / "sample.py").write_text("def foo(): pass\n")
        result = json.loads(code_symbols_tool(str(tmp_path)))
        assert "formatted" in result
        assert "sample.py" in result["formatted"]

    def test_no_symbols_message(self, tmp_path):
        # Directory with only an unsupported file
        (tmp_path / "data.csv").write_text("a,b,c\n1,2,3\n")
        result = json.loads(code_symbols_tool(str(tmp_path)))
        # Should return a message, not crash
        assert "message" in result or result.get("file_count", 0) == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_nonexistent_file(self, tmp_path):
        result = json.loads(code_symbols_tool(str(tmp_path / "missing.py")))
        assert "error" in result

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n")
        result = json.loads(code_symbols_tool(str(f)))
        assert "error" in result or result.get("symbol_count", 0) == 0

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        result = json.loads(code_symbols_tool(str(f)))
        assert result.get("symbol_count", 0) == 0


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_registry_has_code_symbols():
    from tools.registry import registry
    from tools import code_intel  # noqa: F401 — ensure registered
    assert "code_symbols" in registry.get_all_tool_names()
    assert registry.get_toolset_for_tool("code_symbols") == "code_intel"


def test_handler_callable():
    from tools.registry import registry
    from tools import code_intel  # noqa: F401
    entry = registry.get_entry("code_symbols")
    assert entry is not None
    assert callable(entry.handler)
