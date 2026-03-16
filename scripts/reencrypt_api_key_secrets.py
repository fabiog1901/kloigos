import sqlite3

from kloigos import DB_ENGINE, DB_URL
from kloigos.auth import encrypt_api_key_secret


def _is_encrypted(value: bytes | str | None) -> bool:
    if value is None:
        return False
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return raw.startswith(b"\x01")


def _reencrypt_sqlite() -> None:
    with sqlite3.connect(DB_URL) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT access_key, encrypted_secret_access_key FROM api_keys"
        ).fetchall()

        updated = 0
        skipped = 0
        for row in rows:
            access_key = str(row["access_key"])
            secret_value = row["encrypted_secret_access_key"]
            if _is_encrypted(secret_value):
                skipped += 1
                continue

            conn.execute(
                "UPDATE api_keys SET encrypted_secret_access_key = ? WHERE access_key = ?",
                (encrypt_api_key_secret(secret_value), access_key),
            )
            updated += 1

        conn.commit()

    print(f"sqlite migration complete: updated={updated}, already_encrypted={skipped}")


def _reencrypt_postgres() -> None:
    import psycopg

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT access_key, encrypted_secret_access_key FROM api_keys")
            rows = cur.fetchall()

            updated = 0
            skipped = 0
            for access_key, secret_value in rows:
                if _is_encrypted(secret_value):
                    skipped += 1
                    continue

                cur.execute(
                    "UPDATE api_keys SET encrypted_secret_access_key = %s WHERE access_key = %s",
                    (encrypt_api_key_secret(secret_value), access_key),
                )
                updated += 1

        conn.commit()

    print(
        f"postgres migration complete: updated={updated}, already_encrypted={skipped}"
    )


def main() -> None:
    if DB_ENGINE == "sqlite":
        _reencrypt_sqlite()
        return
    if DB_ENGINE == "postgres":
        _reencrypt_postgres()
        return
    raise RuntimeError(f"Unsupported DB_ENGINE: {DB_ENGINE}")


if __name__ == "__main__":
    main()
