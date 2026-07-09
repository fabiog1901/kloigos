import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path.cwd() / ".env", override=True)


KLOIGOS_DB_URL = os.getenv("KLOIGOS_DB_URL", "")
KLOIGOS_MASTER_KEY = os.getenv("KLOIGOS_MASTER_KEY", "")

if KLOIGOS_DB_URL:
    os.environ["KLOIGOS_DB_URL"] = KLOIGOS_DB_URL

if KLOIGOS_MASTER_KEY:
    os.environ["CPKIT_MASTER_KEY"] = KLOIGOS_MASTER_KEY
