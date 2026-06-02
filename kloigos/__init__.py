import os

from dotenv import load_dotenv

load_dotenv(override=True)


DB_URL = os.getenv("DB_URL", "")
