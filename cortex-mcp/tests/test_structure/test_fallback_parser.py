"""Tests for fallback symbol parser."""

from __future__ import annotations

from pathlib import Path

from cortex.structure.fallback_parser import detect_language, parse_file
from cortex.structure.models import Symbol, symbol_id

# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language(Path("app.py")) == "python"

    def test_typescript(self) -> None:
        assert detect_language(Path("index.ts")) == "typescript"

    def test_tsx(self) -> None:
        assert detect_language(Path("App.tsx")) == "typescript"

    def test_javascript(self) -> None:
        assert detect_language(Path("main.js")) == "javascript"

    def test_jsx(self) -> None:
        assert detect_language(Path("App.jsx")) == "javascript"

    def test_go(self) -> None:
        assert detect_language(Path("main.go")) == "go"

    def test_rust(self) -> None:
        assert detect_language(Path("lib.rs")) == "rust"

    def test_cpp(self) -> None:
        assert detect_language(Path("main.cpp")) == "cpp"

    def test_csharp(self) -> None:
        assert detect_language(Path("Program.cs")) == "csharp"

    def test_elixir(self) -> None:
        assert detect_language(Path("router.ex")) == "elixir"

    def test_unknown_returns_none(self) -> None:
        assert detect_language(Path("data.csv")) is None

    def test_case_insensitive(self) -> None:
        assert detect_language(Path("main.PY")) == "python"


# ---------------------------------------------------------------------------
# Symbol model
# ---------------------------------------------------------------------------

class TestSymbolModel:
    def test_deterministic_id(self) -> None:
        s = Symbol(
            name="foo",
            file_path="bar.py",
            symbol_type="function",
            language="python",
        )
        expected = symbol_id("bar.py", "foo", "function")
        assert s.id == expected
        assert len(s.id) == 16

    def test_explicit_id_preserved(self) -> None:
        s = Symbol(
            name="foo",
            file_path="bar.py",
            symbol_type="function",
            language="python",
            id="custom_id",
        )
        assert s.id == "custom_id"


# ---------------------------------------------------------------------------
# Python extraction
# ---------------------------------------------------------------------------

PYTHON_SOURCE = '''\
"""Module docstring."""


def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}"


async def fetch_data(url: str) -> bytes:
    """Fetch remote data."""
    return b""


class Router:
    """HTTP router."""

    def add_route(self, path: str) -> None:
        pass

    async def dispatch(self, request: object) -> object:
        """Dispatch a request."""
        return request
'''


class TestPythonExtraction:
    def _parse(self, source: str = PYTHON_SOURCE) -> list[Symbol]:
        return parse_file(Path("app.py"), source, "python")

    def test_extracts_function(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "greet" in names

    def test_extracts_async_function(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "fetch_data" in names

    def test_extracts_class(self) -> None:
        symbols = self._parse()
        classes = [s for s in symbols if s.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Router"

    def test_extracts_methods(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "add_route" in names
        assert "dispatch" in names

    def test_methods_typed_as_method(self) -> None:
        symbols = self._parse()
        add_route = next(
            s for s in symbols if s.name == "add_route"
        )
        dispatch = next(
            s for s in symbols if s.name == "dispatch"
        )
        assert add_route.symbol_type == "method"
        assert dispatch.symbol_type == "method"

    def test_toplevel_functions_not_method(self) -> None:
        symbols = self._parse()
        greet = next(
            s for s in symbols if s.name == "greet"
        )
        assert greet.symbol_type == "function"

    def test_docstring_extraction(self) -> None:
        symbols = self._parse()
        greet = next(s for s in symbols if s.name == "greet")
        assert greet.docstring == "Return a greeting."

    def test_class_docstring(self) -> None:
        symbols = self._parse()
        router = next(s for s in symbols if s.name == "Router")
        assert router.docstring == "HTTP router."

    def test_async_signature(self) -> None:
        symbols = self._parse()
        fetch = next(s for s in symbols if s.name == "fetch_data")
        assert fetch.signature is not None
        assert fetch.signature.startswith("async def")

    def test_line_start_end(self) -> None:
        symbols = self._parse()
        greet = next(s for s in symbols if s.name == "greet")
        assert greet.line_start == 4
        assert greet.line_end == 6

    def test_class_line_numbers(self) -> None:
        symbols = self._parse()
        router = next(s for s in symbols if s.name == "Router")
        assert router.line_start == 14
        assert router.line_end is not None
        assert router.line_end >= router.line_start

    def test_checksum_nonempty(self) -> None:
        symbols = self._parse()
        for s in symbols:
            assert len(s.checksum) == 16

    def test_language_set(self) -> None:
        symbols = self._parse()
        for s in symbols:
            assert s.language == "python"

    def test_syntax_error_returns_empty(self) -> None:
        result = parse_file(Path("bad.py"), "def (broken", "python")
        assert result == []

    def test_empty_source(self) -> None:
        result = parse_file(Path("empty.py"), "", "python")
        assert result == []


# ---------------------------------------------------------------------------
# TypeScript extraction
# ---------------------------------------------------------------------------

TS_SOURCE = """\
export function initApp(): void {
  console.log("init")
}

export async function fetchData(url: string): Promise<Response> {
  return fetch(url)
}

export class Router {
  navigate(path: string): void {}
}

export interface Config {
  debug: boolean
}

export type AppState = "idle" | "loading"

export const MAX_RETRIES = 3
"""


class TestTypescriptExtraction:
    def _parse(self, source: str = TS_SOURCE) -> list[Symbol]:
        return parse_file(Path("app.ts"), source, "typescript")

    def test_extracts_exported_function(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "initApp" in names

    def test_extracts_async_function(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "fetchData" in names

    def test_extracts_class(self) -> None:
        symbols = self._parse()
        classes = [s for s in symbols if s.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Router"

    def test_extracts_interface(self) -> None:
        symbols = self._parse()
        ifaces = [s for s in symbols if s.symbol_type == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "Config"

    def test_extracts_type(self) -> None:
        symbols = self._parse()
        types = [s for s in symbols if s.symbol_type == "type"]
        assert len(types) == 1
        assert types[0].name == "AppState"

    def test_extracts_constant(self) -> None:
        symbols = self._parse()
        consts = [s for s in symbols if s.symbol_type == "constant"]
        names = [c.name for c in consts]
        assert "MAX_RETRIES" in names

    def test_language_is_typescript(self) -> None:
        symbols = self._parse()
        for s in symbols:
            assert s.language == "typescript"

    def test_js_file_sets_javascript_language(self) -> None:
        source = 'export function hello() { return "hi" }\n'
        symbols = parse_file(Path("app.js"), source, "javascript")
        assert len(symbols) >= 1
        assert symbols[0].language == "javascript"

    def test_line_numbers(self) -> None:
        symbols = self._parse()
        init = next(s for s in symbols if s.name == "initApp")
        assert init.line_start == 1

    def test_signature_truncated(self) -> None:
        long_name = "x" * 300
        source = f"export function {long_name}(): void {{}}\n"
        symbols = parse_file(Path("long.ts"), source, "typescript")
        assert len(symbols) == 1
        assert symbols[0].signature is not None
        assert len(symbols[0].signature) <= 200


# ---------------------------------------------------------------------------
# Go extraction
# ---------------------------------------------------------------------------

GO_SOURCE = """\
package main

import "fmt"

func main() {
    fmt.Println("hello")
}

func (s *Server) Start(port int) error {
    return nil
}

type Config struct {
    Debug bool
    Port  int
}

type Handler interface {
    ServeHTTP(w Writer, r *Request)
}
"""


class TestGoExtraction:
    def _parse(self, source: str = GO_SOURCE) -> list[Symbol]:
        return parse_file(Path("main.go"), source, "go")

    def test_extracts_function(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "main" in names

    def test_extracts_method(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "Start" in names

    def test_extracts_struct(self) -> None:
        symbols = self._parse()
        structs = [s for s in symbols if s.symbol_type == "class"]
        names = [s.name for s in structs]
        assert "Config" in names

    def test_extracts_interface(self) -> None:
        symbols = self._parse()
        ifaces = [s for s in symbols if s.symbol_type == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "Handler"

    def test_language_is_go(self) -> None:
        symbols = self._parse()
        for s in symbols:
            assert s.language == "go"

    def test_line_numbers(self) -> None:
        symbols = self._parse()
        main_fn = next(s for s in symbols if s.name == "main")
        assert main_fn.line_start == 5

    def test_struct_line_number(self) -> None:
        symbols = self._parse()
        config = next(s for s in symbols if s.name == "Config")
        assert config.line_start == 13


# ---------------------------------------------------------------------------
# Rust extraction
# ---------------------------------------------------------------------------

RUST_SOURCE = """\
pub fn process(data: &[u8]) -> Result<(), Error> {
    Ok(())
}

pub async fn fetch(url: &str) -> Response {
    todo!()
}

pub struct Config {
    debug: bool,
}

pub enum Status {
    Ok,
    Error(String),
}

pub trait Handler {
    fn handle(&self) -> Response;
}

impl Config {
    fn new() -> Self {
        Config { debug: false }
    }
}
"""


class TestRustExtraction:
    def _parse(self, source: str = RUST_SOURCE) -> list[Symbol]:
        return parse_file(Path("lib.rs"), source, "rust")

    def test_extracts_pub_fn(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "process" in names

    def test_extracts_async_fn(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols]
        assert "fetch" in names

    def test_extracts_struct(self) -> None:
        symbols = self._parse()
        structs = [s for s in symbols if s.name == "Config"]
        assert len(structs) >= 1

    def test_extracts_enum(self) -> None:
        symbols = self._parse()
        enums = [s for s in symbols if s.symbol_type == "type"]
        names = [e.name for e in enums]
        assert "Status" in names

    def test_extracts_trait(self) -> None:
        symbols = self._parse()
        traits = [s for s in symbols if s.symbol_type == "interface"]
        assert len(traits) == 1
        assert traits[0].name == "Handler"

    def test_language_is_rust(self) -> None:
        symbols = self._parse()
        for s in symbols:
            assert s.language == "rust"

    def test_line_numbers(self) -> None:
        symbols = self._parse()
        process = next(s for s in symbols if s.name == "process")
        assert process.line_start == 1


# ---------------------------------------------------------------------------
# Unsupported language
# ---------------------------------------------------------------------------

class TestUnsupportedLanguage:
    def test_returns_empty(self) -> None:
        result = parse_file(Path("style.css"), "body { color: red }", "css")
        assert result == []


# ---------------------------------------------------------------------------
# parse_file integration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Python route detection
# ---------------------------------------------------------------------------

PYTHON_ROUTES_SOURCE = '''\
from fastapi import APIRouter

app = FastAPI()
router = APIRouter()


@app.get("/config")
def get_config():
    return {"debug": True}


@app.post("/users")
async def create_user(name: str):
    return {"name": name}


@router.put("/items/{item_id}")
def update_item(item_id: int):
    pass


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    pass


@app.patch("/users/{user_id}")
def patch_user(user_id: int):
    pass


@app.route("/health")
def health_check():
    return "ok"


@blueprint.route("/legacy")
def legacy_endpoint():
    return "legacy"


@some_decorator
def not_a_route():
    pass
'''


class TestPythonRouteDetection:
    def _parse(self, source: str = PYTHON_ROUTES_SOURCE) -> list[Symbol]:
        return parse_file(Path("api.py"), source, "python")

    def test_app_get_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "GET /config" in names

    def test_app_post_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "POST /users" in names

    def test_router_put_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "PUT /items/{item_id}" in names

    def test_router_delete_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "DELETE /items/{item_id}" in names

    def test_app_patch_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "PATCH /users/{user_id}" in names

    def test_app_route_defaults_to_route_name(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "ROUTE /health" in names

    def test_blueprint_route_detected(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "ROUTE /legacy" in names

    def test_non_route_decorator_ignored(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert not any("not_a_route" in n for n in names)

    def test_route_language_is_python(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        assert all(r.language == "python" for r in routes)

    def test_function_still_extracted_alongside_route(self) -> None:
        symbols = self._parse()
        funcs = [s for s in symbols if s.symbol_type == "function"]
        names = [f.name for f in funcs]
        assert "get_config" in names


# ---------------------------------------------------------------------------
# TS/JS route detection
# ---------------------------------------------------------------------------

TS_ROUTES_SOURCE = """\
import express from 'express'

const app = express()
const router = express.Router()

app.get('/config', (req, res) => {
  res.json({ debug: true })
})

app.post('/users', async (req, res) => {
  res.json({ name: req.body.name })
})

router.put('/items/:id', (req, res) => {
  res.send('updated')
})

router.delete('/items/:id', (req, res) => {
  res.send('deleted')
})

router.patch('/users/:id', (req, res) => {
  res.send('patched')
})
"""


class TestTsRouteDetection:
    def _parse(self, source: str = TS_ROUTES_SOURCE) -> list[Symbol]:
        return parse_file(Path("server.ts"), source, "typescript")

    def test_app_get_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "GET /config" in names

    def test_app_post_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "POST /users" in names

    def test_router_put_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "PUT /items/:id" in names

    def test_router_delete_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "DELETE /items/:id" in names

    def test_router_patch_creates_route(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        names = [r.name for r in routes]
        assert "PATCH /users/:id" in names

    def test_route_language_is_typescript(self) -> None:
        symbols = self._parse()
        routes = [s for s in symbols if s.symbol_type == "route"]
        assert all(r.language == "typescript" for r in routes)

    def test_js_routes_set_javascript_language(self) -> None:
        source = "app.get('/health', (req, res) => res.send('ok'))\n"
        symbols = parse_file(Path("app.js"), source, "javascript")
        routes = [s for s in symbols if s.symbol_type == "route"]
        assert len(routes) == 1
        assert routes[0].language == "javascript"


# ---------------------------------------------------------------------------
# TS/JS class method extraction
# ---------------------------------------------------------------------------

TS_METHODS_SOURCE = """\
export class Router {
  addRoute(path: string): void {
    this.routes.push(path)
  }

  async dispatch(req: Request): Promise<Response> {
    return new Response()
  }

  private handleError(err: Error): void {
    console.error(err)
  }

  get count(): number {
    return this.routes.length
  }
}

function standalone() {
  if (true) {
    for (let i = 0; i < 10; i++) {
      while (false) {
        switch (x) {
        }
      }
    }
  }
}
"""


class TestTsMethodExtraction:
    def _parse(self, source: str = TS_METHODS_SOURCE) -> list[Symbol]:
        return parse_file(Path("router.ts"), source, "typescript")

    def test_extracts_class_method(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols if s.symbol_type == "method"]
        assert "addRoute" in names

    def test_extracts_async_method(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols if s.symbol_type == "method"]
        assert "dispatch" in names

    def test_extracts_private_method(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols if s.symbol_type == "method"]
        assert "handleError" in names

    def test_keywords_not_extracted(self) -> None:
        symbols = self._parse()
        methods = [s for s in symbols if s.symbol_type == "method"]
        names = [m.name for m in methods]
        for keyword in ("if", "for", "while", "switch"):
            assert keyword not in names

    def test_constructor_not_extracted(self) -> None:
        source = """\
export class Foo {
  constructor(x: number) {
    this.x = x
  }
}
"""
        symbols = parse_file(Path("foo.ts"), source, "typescript")
        methods = [s for s in symbols if s.symbol_type == "method"]
        names = [m.name for m in methods]
        assert "constructor" not in names

    def test_getter_extracted_as_method(self) -> None:
        symbols = self._parse()
        names = [s.name for s in symbols if s.symbol_type == "method"]
        assert "count" in names

    def test_method_language_is_typescript(self) -> None:
        symbols = self._parse()
        methods = [s for s in symbols if s.symbol_type == "method"]
        assert all(m.language == "typescript" for m in methods)


# ---------------------------------------------------------------------------
# Elixir extraction
# ---------------------------------------------------------------------------

ELIXIR_SOURCE = '''
defmodule MyApp.Router do
  use Plug.Router

  plug :match
  plug :dispatch

  def hello(conn, _opts) do
    send_resp(conn, 200, "Hello")
  end

  defp validate(params) do
    Map.has_key?(params, :name)
  end

  get "/api/status" do
    send_resp(conn, 200, "ok")
  end

  post "/api/users" do
    send_resp(conn, 201, "created")
  end
end

defmodule MyApp.GenServerWorker do
  use GenServer

  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts)
  end

  def init(state) do
    {:ok, state}
  end

  def handle_call(:get, _from, state) do
    {:reply, state, state}
  end
end
'''


class TestElixirExtraction:
    def test_finds_modules(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        modules = [s for s in syms if s.symbol_type == "module"]
        names = {s.name for s in modules}
        assert "MyApp.Router" in names
        assert "MyApp.GenServerWorker" in names

    def test_finds_public_functions(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        fns = [s for s in syms if s.symbol_type == "function"]
        names = {s.name for s in fns}
        assert "hello" in names
        assert "start_link" in names
        assert "init" in names
        assert "handle_call" in names

    def test_finds_private_functions(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        privates = [s for s in syms if s.symbol_type == "private_function"]
        names = {s.name for s in privates}
        assert "validate" in names

    def test_finds_routes(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        routes = [s for s in syms if s.symbol_type == "route"]
        names = {s.name for s in routes}
        assert "GET /api/status" in names
        assert "POST /api/users" in names

    def test_language_is_elixir(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        assert all(s.language == "elixir" for s in syms)

    def test_line_numbers(self) -> None:
        syms = parse_file(Path("router.ex"), ELIXIR_SOURCE, "elixir")
        modules = [s for s in syms if s.name == "MyApp.Router"]
        assert len(modules) == 1
        assert modules[0].line_start > 0

    def test_exs_extension(self) -> None:
        syms = parse_file(Path("test_helper.exs"), ELIXIR_SOURCE, "elixir")
        assert len(syms) > 0

    def test_empty_source(self) -> None:
        syms = parse_file(Path("empty.ex"), "", "elixir")
        assert syms == []

    def test_unsupported_returns_empty(self) -> None:
        syms = parse_file(Path("data.csv"), "col1,col2", "csv")
        assert syms == []


class TestParseFileIntegration:
    def test_deterministic_ids(self) -> None:
        source = "def foo():\n    pass\n"
        s1 = parse_file(Path("a.py"), source, "python")
        s2 = parse_file(Path("a.py"), source, "python")
        assert s1[0].id == s2[0].id

    def test_different_files_different_ids(self) -> None:
        source = "def foo():\n    pass\n"
        s1 = parse_file(Path("a.py"), source, "python")
        s2 = parse_file(Path("b.py"), source, "python")
        assert s1[0].id != s2[0].id
