import psycopg

from kloigos import DB_URL
from kloigos.util import encrypt_api_key_secret


def _is_encrypted(value: bytes | str | None) -> bool:
    if value is None:
        return False
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return raw.startswith(b"\x01")


with psycopg.connect(DB_URL, autocommit=True) as conn:
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


print(
    f"postgres migration complete: updated={updated}, already_encrypted={skipped}"
)

