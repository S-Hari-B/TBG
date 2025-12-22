"""Entry-point for launching the CLI application."""
from __future__ import annotations

from .presentation.cli.app import main as cli_main


def main() -> None:
    """Run the CLI presentation layer."""
    cli_main()


if __name__ == "__main__":
    main()

