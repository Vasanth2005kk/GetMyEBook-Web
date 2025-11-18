import os
import subprocess
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from dotenv import load_dotenv

from . import logger

log = logger.create()

# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv('/home/vasanth/GetMyEBook-Web/.env')

DB_USER     = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")  # RAW PASSWORD HERE
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DATABASENAME_CALIBRE", "metadatadb")

# SQLITE_PATH = "/home/vasanth/metadata.db"


# ---------------------------
# Auto install pgloader (Linux only)
# ---------------------------
def ensure_pgloader_installed():
    try:
        subprocess.run(["pgloader", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info("✔ pgloader already installed.")
    except FileNotFoundError:
        log.info("⚠ pgloader not found. Installing...")
        subprocess.run(["sudo", "apt-get", "update", "-y"])
        subprocess.run(["sudo", "apt-get", "install", "-y", "pgloader"])
        log.info("✔ pgloader installed successfully.")


# ---------------------------
# Complete migration workflow
# ---------------------------
def migrate_sqlite_to_postgres(SQLITE_PATH):
    ensure_pgloader_installed()

    # Password encoding for URL
    encoded_pw = urllib.parse.quote_plus(DB_PASSWORD)

    POSTGRES_ADMIN_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/postgres"
    TARGET_PGLOADER_URL = f"postgresql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME.lower()}"

    log.info("\nPostgreSQL Admin URL =", POSTGRES_ADMIN_URL)
    log.info("pgloader Target URL   =", TARGET_PGLOADER_URL)

    # Create database
    engine = create_engine(POSTGRES_ADMIN_URL, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {DB_NAME};"))
            log.info(f"✔ Database '{DB_NAME}' created.")
    except ProgrammingError:
        log.info(f"✔ Database '{DB_NAME}' already exists.")

    # Run pgloader
    log.info("\nRunning migration using pgloader...\n")

    command = [
        "pgloader",
        f"sqlite:///{SQLITE_PATH}",
        TARGET_PGLOADER_URL
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    log.info("=========== PGLOADER OUTPUT ===========")
    log.info(result.stdout)
    log.info("=========== PGLOADER ERRORS ===========")
    log.info(result.stderr)


# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    migrate_sqlite_to_postgres()
