"""Kloigos command-line entrypoint."""

import argparse
import base64
import os
import secrets
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from cpkit.cli import ApplicationCLI
from pgembed import PostgresServer, get_server
from psycopg import connect
from psycopg.errors import DuplicateDatabase


def _package_path(relative_path: str) -> Path:
    return Path(str(files("kloigos").joinpath(relative_path)))


class KloigosCLI(ApplicationCLI):
    """Command-line interface for Kloigos."""

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=self.app_name)
        subparsers = parser.add_subparsers(dest="command", required=True)

        init = subparsers.add_parser("init", help="Initialize database schemas.")
        init.set_defaults(handler=self.init)

        server = subparsers.add_parser("serve", help="Run the FastAPI application.")
        server.add_argument("--host", default="0.0.0.0")
        server.add_argument("--port", type=int, default=8000)
        server.add_argument("--reload", action="store_true")
        server.add_argument("--log-level", default="info")
        server.set_defaults(handler=self.serve)

        demo = subparsers.add_parser(
            "demo",
            help="Run Kloigos with an embedded local Postgres database.",
        )
        demo.add_argument(
            "--data-dir",
            type=Path,
            default=Path.home() / ".local/share/kloigos/demo",
            help="Directory used for demo database and generated secrets.",
        )
        demo.add_argument("--host", default="127.0.0.1")
        demo.add_argument("--port", type=int, default=8000)
        demo.add_argument("--reload", action="store_true")
        demo.add_argument("--log-level", default="info")
        demo.set_defaults(handler=self.demo)
        return parser

    def demo(self, args: argparse.Namespace) -> int:
        """Run Kloigos against a local embedded Postgres instance."""
        data_dir = args.data_dir.expanduser().resolve()
        pgdata = data_dir / "pgdata"
        key_path = data_dir / "kloigos-master.key"
        data_dir.mkdir(parents=True, exist_ok=True)
        _configure_pgembed_runtime(PostgresServer, data_dir / "runtime")

        server = get_server(pgdata)
        admin_db_url = server.get_uri(database="postgres")
        db_url = server.get_uri(database="kloigos")

        with connect(admin_db_url, autocommit=True) as conn:
            try:
                conn.execute("CREATE DATABASE kloigos")
            except DuplicateDatabase:
                pass

        _set_kloigos_env(
            db_url=db_url,
            master_key=_read_or_create_master_key(key_path),
        )

        _init_demo_database(self)
        _print_demo_env(data_dir, pgdata, key_path, db_url)
        return self.serve(args)


def _read_or_create_master_key(path: Path) -> str:
    if path.exists():
        return path.read_text().strip()

    master_key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    path.write_text(f"{master_key}\n")
    path.chmod(0o600)
    return master_key


def _configure_pgembed_runtime(postgres_server_class: type, runtime_path: Path) -> None:
    runtime_path.mkdir(parents=True, exist_ok=True)
    postgres_server_class.runtime_path = runtime_path
    postgres_server_class.lock_path = runtime_path / ".lockfile"
    postgres_server_class._lock = postgres_server_class.fasteners.InterProcessLock(
        postgres_server_class.lock_path
    )


def _set_kloigos_env(*, db_url: str, master_key: str) -> None:
    os.environ["KLOIGOS_DB_URL"] = db_url
    os.environ["KLOIGOS_MASTER_KEY"] = master_key
    os.environ["CPKIT_MASTER_KEY"] = master_key

    package = sys.modules.get("kloigos")
    if package is not None:
        package.KLOIGOS_DB_URL = db_url
        package.KLOIGOS_MASTER_KEY = master_key


def _init_demo_database(cli: ApplicationCLI) -> None:
    print("Initializing demo database.")
    cli.init(argparse.Namespace())


def _print_demo_env(data_dir: Path, pgdata: Path, key_path: Path, db_url: str) -> None:
    print()
    print("Kloigos demo environment")
    print(f"Data directory: {data_dir}")
    print(f"Postgres data: {pgdata}")
    print(f"Master key file: {key_path}")
    print()
    print(f"KLOIGOS_DB_URL='{db_url}'")
    print(f"KLOIGOS_MASTER_KEY='{os.environ['KLOIGOS_MASTER_KEY']}'")
    print()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Kloigos CLI."""
    cli = KloigosCLI(
        app_name="kloigos",
        app_import="kloigos.main:app",
        db_url_env="KLOIGOS_DB_URL",
        app_ddl_paths=(_package_path("resources/database/ddl.sql"),),
        app_playbook_dirs=(_package_path("resources/playbooks"),),
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
