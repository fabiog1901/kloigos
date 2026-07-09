"""Kloigos command-line entrypoint."""

import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from cpkit.cli import ApplicationCLI


def _package_path(relative_path: str) -> Path:
    return Path(str(files("kloigos").joinpath(relative_path)))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Kloigos CLI."""
    cli = ApplicationCLI(
        app_name="kloigos",
        app_import="kloigos.main:app",
        db_url_env="KLOIGOS_DB_URL",
        app_ddl_paths=(_package_path("resources/database/ddl.sql"),),
        app_schema_checks=(
            "public.servers",
            "public.compute_units",
        ),
    )
    try:
        return cli.main(argv)
    except RuntimeError as exc:
        if str(exc).endswith(" is not set."):
            print(
                f"{exc} Set it in .env or export it before running kloigos.",
                file=sys.stderr,
            )
            return 1
        raise
