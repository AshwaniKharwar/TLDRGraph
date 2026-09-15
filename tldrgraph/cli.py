"""CLI for the source-backed TLDRGraph Workflow Explorer."""

from __future__ import annotations

import functools
import http.server
import os
import socketserver
import threading
import webbrowser

import click

from .cli_pipeline import init_pipeline
from .installer import ensure_gitignore, gitignore_warnings, install_agent_rules
from .visualizer import generate_visualizer_html


@click.group()
def cli():
    """Generate and explore source-backed feature workflows."""


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable status.")
def init(path: str, as_json: bool) -> None:
    """Create or refresh the source-backed workflow catalog."""
    init_pipeline(path, as_json)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def _serve(root: str, html_path: str, port: int, open_browser: bool) -> None:
    relative = os.path.relpath(html_path, root).replace(os.sep, "/")
    handler = functools.partial(_QuietHandler, directory=root)
    socketserver.TCPServer.allow_reuse_address = True
    try:
        server = socketserver.TCPServer(("127.0.0.1", port), handler)
    except OSError as error:
        raise click.ClickException(f"Could not bind port {port}: {error}") from error
    url = f"http://127.0.0.1:{port}/{relative}"
    click.echo(f"Serving {root} at {url}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nWorkflow Explorer stopped.")
    finally:
        server.server_close()


@cli.command(name="ui")
@click.option("--path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--serve", is_flag=True, help="Serve the repository for live source access.")
@click.option("--port", default=8777, show_default=True)
@click.option("--open/--no-open", "open_browser", default=True, show_default=True)
def ui(path: str, serve: bool, port: int, open_browser: bool) -> None:
    """Generate the standalone Workflow Explorer."""
    root = os.path.abspath(path)
    output = generate_visualizer_html(root)
    click.echo(f"Workflow Explorer: {output}")
    if serve:
        _serve(root, output, port, open_browser)


@cli.command()
@click.option("--path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--all-agents", is_flag=True, help="Install the workflow for every known coding agent.")
def install(path: str, all_agents: bool) -> None:
    """Install the source-backed workflow handshake for coding agents."""
    gitignore = ensure_gitignore(path)
    result = install_agent_rules(path, all_agents=all_agents)
    click.echo("Installed TLDRGraph agent workflow:")
    for name, output in result.items():
        click.echo(f"  {name}: {output}")
    click.echo(f"  gitignore: {gitignore['path']} ({gitignore['status']})")
    for warning in gitignore_warnings(path):
        click.echo(f"Warning: {warning}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
