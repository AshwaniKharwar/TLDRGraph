"""
Tests for the visualizer's source slicer.

The slicer decides what code the visualizer shows, so the property that matters
most is that it never shows the *wrong* symbol: a snapshot can outlive the edits
made since it was written, and a stale line number must not be trusted blindly.
"""

import textwrap

from tldrgraph.visualizer.source import (
    SourceIndex,
    language_for,
    parse_line_number,
    symbol_name,
)


PY_SAMPLE = textwrap.dedent(
    '''\
    import os


    def helper(a, b):
        """Adds."""
        return a + b


    class Widget:
        """A widget."""

        def render(self, ctx):
            total = helper(1, 2)
            if total:
                return ctx
            return None

        def resize(self, w, h):
            return (w, h)


    def trailing():
        return 1
    '''
)

JS_SAMPLE = textwrap.dedent(
    """\
    const x = 1;

    function compute(a, b) {
      if (a > b) {
        return a;
      }
      return b;
    }

    export function after() {
      return 0;
    }
    """
)

PRISMA_SAMPLE = textwrap.dedent(
    """\
    datasource db {
      provider = "postgresql"
      url      = env("DATABASE_URL")
    }

    model Project {
      id        String @id
      name      String
      user      User   @relation(fields: [userId], references: [id])
      userId    String
    }

    model User {
      id String @id
    }
    """
)

ROUTE_SAMPLE = textwrap.dedent(
    """\
    import { Router } from "express";

    const router = Router();

    router.get("/containers/create", listContainers);

    router.post("/containers/create", async (req, res) => {
      await createContainer(req.body);
      return res.json({ ok: true });
    });

    app.post(
      '/single-quoted',
      handler,
    );

    router.delete("/gone", removeContainer);
    """
)


def _index(tmp_path, name, body):
    (tmp_path / name).write_text(body, encoding="utf-8")
    return SourceIndex(str(tmp_path))


def test_parse_line_number_forms():
    assert parse_line_number("L88") == 88
    assert parse_line_number("88") == 88
    assert parse_line_number("L88-120") == 88
    assert parse_line_number("") is None
    assert parse_line_number(None) is None
    assert parse_line_number("nonsense") is None


def test_symbol_name_strips_qualifiers_and_parens():
    assert symbol_name(".load_or_extract()") == "load_or_extract"
    assert symbol_name("GraphLoader.load_or_extract()") == "load_or_extract"
    assert symbol_name("Widget") == "Widget"
    assert symbol_name("__init__()") == "__init__"


def test_language_detection():
    assert language_for("a/b/c.py") == "python"
    assert language_for("app/main.tsx") == "typescript"
    assert language_for("Makefile") == "plain"


def test_slices_python_function_to_its_dedent(tmp_path):
    idx = _index(tmp_path, "mod.py", PY_SAMPLE)
    got = idx.slice_symbol("mod.py", "L4", "helper")

    assert got["start"] == 4
    assert got["code"].startswith("def helper(a, b):")
    assert "return a + b" in got["code"]
    # Must stop before the next top-level statement.
    assert "class Widget" not in got["code"]
    assert got["language"] == "python"
    assert got["relocated"] is False


def test_slices_python_method_without_swallowing_the_next_one(tmp_path):
    idx = _index(tmp_path, "mod.py", PY_SAMPLE)
    got = idx.slice_symbol("mod.py", "L12", "render")

    assert "def render(self, ctx):" in got["code"]
    assert "return None" in got["code"]
    assert "def resize" not in got["code"]


def test_slices_brace_language_by_balancing_braces(tmp_path):
    idx = _index(tmp_path, "app.js", JS_SAMPLE)
    got = idx.slice_symbol("app.js", "L3", "compute")

    assert got["code"].startswith("function compute(a, b) {")
    assert got["code"].rstrip().endswith("}")
    assert "export function after" not in got["code"]
    assert got["language"] == "javascript"


def test_slices_prisma_model_declaration(tmp_path):
    idx = _index(tmp_path, "schema.prisma", PRISMA_SAMPLE)
    got = idx.slice_symbol("schema.prisma", "L6", "Project")

    assert got["start"] == 6
    assert got["code"].startswith("model Project {")
    assert "userId    String" in got["code"]
    assert "model User" not in got["code"]


def test_stale_line_is_re_resolved_by_symbol_name(tmp_path):
    """A snapshot line pointing at unrelated code must not be trusted."""
    idx = _index(tmp_path, "mod.py", PY_SAMPLE)
    got = idx.slice_symbol("mod.py", "L1", "resize")

    assert got["relocated"] is True
    assert got["start"] == 18
    assert "def resize(self, w, h):" in got["code"]


def test_unknown_symbol_yields_no_code_rather_than_wrong_code(tmp_path):
    idx = _index(tmp_path, "mod.py", PY_SAMPLE)
    assert idx.slice_symbol("mod.py", "L1", "does_not_exist") is None


def test_locates_route_registration_by_method_and_path(tmp_path):
    idx = _index(tmp_path, "routes.ts", ROUTE_SAMPLE)
    got = idx.slice_symbol(
        "routes.ts", "L7", "POST /containers/create", "post", "/containers/create"
    )

    assert got["start"] == 7
    assert 'router.post("/containers/create"' in got["code"]
    assert 'router.get("/containers/create"' not in got["code"]


def test_locates_single_quoted_multiline_route_registration(tmp_path):
    idx = _index(tmp_path, "routes.ts", ROUTE_SAMPLE)
    got = idx.locate_symbol("routes.ts", "L12", "POST /single-quoted", "post", "/single-quoted")

    assert got["start"] == 12
    assert got["relocated"] is False


def test_stale_route_line_is_re_resolved_by_method_and_path(tmp_path):
    idx = _index(tmp_path, "routes.ts", ROUTE_SAMPLE)
    got = idx.locate_symbol("routes.ts", "L1", "POST /containers/create", "post", "/containers/create")

    assert got["start"] == 7
    assert got["relocated"] is True


def test_mounted_route_resolves_to_local_router_literal(tmp_path):
    idx = _index(tmp_path, "routes.ts", 'router.post("/create", handler);\n')
    got = idx.locate_symbol("routes.ts", "L7", "POST /containers/create", "post", "/containers/create")

    assert got["start"] == 1


def test_missing_route_yields_no_code_rather_than_wrong_route(tmp_path):
    idx = _index(tmp_path, "routes.ts", ROUTE_SAMPLE)

    assert idx.slice_symbol("routes.ts", "L7", "POST /missing", "post", "/missing") is None


def test_missing_file_and_pseudo_paths_are_safe(tmp_path):
    idx = _index(tmp_path, "mod.py", PY_SAMPLE)
    assert idx.slice_symbol("nope.py", "L4", "helper") is None
    assert idx.slice_symbol("", "L4", "helper") is None
    assert idx.slice_symbol("root", "L4", "helper") is None


def test_long_symbol_is_capped(tmp_path, monkeypatch):
    body = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(200))
    idx = _index(tmp_path, "big.py", body)
    got = idx.slice_symbol("big.py", "L1", "big")

    assert got["truncated"] is True
    assert len(got["code"].split("\n")) <= 80


def test_decorators_are_included_as_leading_context(tmp_path):
    body = textwrap.dedent(
        '''\
        import functools


        @functools.cache
        def cached(value):
            return value
        '''
    )
    idx = _index(tmp_path, "deco.py", body)
    got = idx.slice_symbol("deco.py", "L5", "cached")

    assert got["code"].startswith("@functools.cache")
    assert got["start"] == 4
