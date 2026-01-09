import os

from dotenv import load_dotenv

load_dotenv(override=True)


DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()
DB_URL = os.getenv("DB_URL", "sqlite.kloigos")

# count of ports assigned for each allocated cpu.
#
# 64000 total avilable ports per server / 512 max_cpus_per_server = 125 ports_per_cpu
PORTS_PER_CPU = int(os.getenv("PORTS_PER_CPU", 0))
# We assign ports to compute units starting from base_port
BASE_PORT = int(os.getenv("BASE_PORT", 0))
# Kloigos supports server up to these many CPUs
MAX_CPUS_PER_SERVER = int(os.getenv("MAX_CPUS_PER_SERVER", 0))
